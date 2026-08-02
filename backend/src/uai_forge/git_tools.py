"""Git workflow operations for explicitly mounted development Agents.

``tool.git`` is a structured Git adapter rather than an arbitrary shell
wrapper.  It exposes the ordinary repository workflow (status, diff, pull,
commit and push) while the repository and credential remain deployment
configuration.  Credentials are resolved through the private tool-credential
port at invocation time and are only placed in the short-lived child-process
environment.
"""

from __future__ import annotations

import asyncio
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple
from .models import PluginKind, PluginManifest, ToolBinding
from .ports import ToolPlugin


GIT_MANIFEST = PluginManifest(
    id="tool.git",
    kind=PluginKind.TOOL,
    display_name="Git",
    version="1.0.0",
    description=(
        "Run the normal status, diff, pull, commit and push workflow for the configured repository."
    ),
    capabilities=[
        "local_process",
        "bounded_output",
        "credential_ref",
        "pull",
        "commit",
        "push",
        "external_side_effects",
        "auditable",
    ],
    config_schema={
        "type": "object",
        "properties": {
            "root_path": {"type": "string", "minLength": 1, "maxLength": 512},
            "credential_ref": {"type": "string", "minLength": 1, "maxLength": 120},
            "remote_name": {
                "type": "string",
                "pattern": "^[A-Za-z0-9._-]{1,32}$",
            },
            "timeout_seconds": {
                "type": "number",
                "minimum": 5,
                "maximum": 600,
            },
            "max_output_bytes": {
                "type": "integer",
                "minimum": 1_024,
                "maximum": 200_000,
            },
            "author_name": {"type": "string", "minLength": 1, "maxLength": 120},
            "author_email": {"type": "string", "minLength": 3, "maxLength": 254},
        },
        "required": [
            "root_path",
            "credential_ref",
        ],
        "additionalProperties": False,
    },
)


ProcessRunner = Callable[..., Awaitable[asyncio.subprocess.Process]]
_ACTIONS = {"status", "diff", "pull", "push", "commit", "commit_and_push"}
_REMOTE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,32}$")
_SECRET_REF = re.compile(r"(?i)^(?:gh[pousr]|github_pat|xox[baprs])[-_]")
_SECRET_TEXT_PATTERNS = (
    re.compile(
        r"(?i)(\b(?:api[_-]?key|authorization|access[_-]?token|refresh[_-]?token|"
        r"password|private[_-]?key|secret)\b\s*[:=]\s*)([^\s,;]+)"
    ),
    re.compile(r"(?i)(\bBearer\s+)([^\s]+)"),
    re.compile(r"\b(?:sk|ghp|github_pat|xoxb|xoxp)[-_][A-Za-z0-9_-]{12,}\b"),
)


def _redact_text(value: str, secret: Optional[str] = None) -> str:
    result = value or ""
    if secret:
        result = result.replace(secret, "<redacted>")
    for pattern in _SECRET_TEXT_PATTERNS:
        if pattern.groups >= 2:
            result = pattern.sub(lambda match: f"{match.group(1)}<redacted>", result)
        else:
            result = pattern.sub("<redacted>", result)
    return result


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        candidate = default
    return max(minimum, min(maximum, candidate))


def _bounded_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        candidate = float(value)
    except (TypeError, ValueError):
        candidate = default
    return max(minimum, min(maximum, candidate))


async def _read_limited(
    reader: Optional[asyncio.StreamReader],
    limit: int,
) -> Tuple[bytes, bool]:
    if reader is None:
        return b"", False
    chunks: List[bytes] = []
    seen = 0
    truncated = False
    while True:
        chunk = await reader.read(64 * 1024)
        if not chunk:
            break
        if seen < limit:
            chunks.append(chunk[: limit - seen])
        seen += len(chunk)
        if seen > limit:
            truncated = True
    return b"".join(chunks), truncated


def _parse_nul_names(raw: str) -> List[str]:
    return [item for item in raw.split("\0") if item]


class GitTool(ToolPlugin):
    manifest = GIT_MANIFEST
    name = "git"
    description = (
        "Inspect the configured repository, pull changes, or commit and push the current branch."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": sorted(_ACTIONS),
                "description": "Choose status, diff, pull, push, commit, or commit_and_push.",
            },
            "commit_message": {
                "type": "string",
                "maxLength": 240,
                "description": "One-line commit message; used by commit or commit_and_push.",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        binding: ToolBinding,
        *,
        process_runner: Optional[ProcessRunner] = None,
    ) -> None:
        self.binding = binding
        self._process_runner = process_runner or asyncio.create_subprocess_exec

    @property
    def config(self) -> Dict[str, Any]:
        return self.binding.config

    def _root(self) -> Path:
        raw = str(self.config.get("root_path", "")).strip()
        root = Path(raw)
        if not root.is_absolute():
            raise ValueError("git.root_path_must_be_absolute")
        try:
            resolved = root.resolve(strict=True)
        except OSError as exc:
            raise ValueError("git.root_path_unavailable") from exc
        if not resolved.is_dir() or resolved == Path("/"):
            raise ValueError("git.root_path_invalid")
        return resolved

    def _remote_name(self) -> str:
        remote = str(self.config.get("remote_name", "origin")).strip()
        if not _REMOTE_NAME.fullmatch(remote):
            raise ValueError("git.remote_name_invalid")
        return remote

    def _public_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: result[key]
            for key in (
                "exit_code",
                "stdout",
                "stderr",
                "timed_out",
                "truncated",
                "duration_ms",
            )
        }

    @staticmethod
    def _failure(action: str, error: str, **extra: Any) -> Dict[str, Any]:
        return {"action": action, "ok": False, "error": error, **extra}

    async def _terminate(self, process: asyncio.subprocess.Process) -> None:
        try:
            if process.returncode is None:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=2)
        except (asyncio.TimeoutError, ProcessLookupError):
            try:
                process.kill()
                await process.wait()
            except (ProcessLookupError, OSError):
                return

    async def _run(
        self,
        root: Path,
        command: Sequence[str],
        *,
        secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        timeout = _bounded_float(self.config.get("timeout_seconds"), 120, 5, 600)
        output_limit = _bounded_int(
            self.config.get("max_output_bytes"),
            120_000,
            1_024,
            200_000,
        )
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": "/nonexistent",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
        }
        temporary_directory: Optional[tempfile.TemporaryDirectory[str]] = None
        if secret:
            temporary_directory = tempfile.TemporaryDirectory(prefix="uai-git-askpass-")
            askpass = Path(temporary_directory.name) / "askpass.sh"
            askpass.write_text(
                "#!/bin/sh\n"
                "case \"${1:-}\" in\n"
                "  *[Uu]sername*) printf '%s\\n' 'x-access-token' ;;\n"
                "  *) printf '%s\\n' \"${UAI_GIT_TOKEN:-}\" ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            askpass.chmod(0o700)
            env.update(
                {
                    "GIT_ASKPASS": str(askpass),
                    "UAI_GIT_TOKEN": secret,
                }
            )
        started = time.monotonic()
        try:
            try:
                process = await self._process_runner(
                    *command,
                    cwd=str(root),
                    env=env,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout_task = asyncio.create_task(_read_limited(process.stdout, output_limit))
                    stderr_task = asyncio.create_task(_read_limited(process.stderr, output_limit))
                    wait_task = asyncio.create_task(process.wait())
                    try:
                        (stdout, stdout_truncated), (stderr, stderr_truncated), exit_code = await asyncio.wait_for(
                            asyncio.gather(stdout_task, stderr_task, wait_task),
                            timeout=timeout,
                        )
                        timed_out = False
                    except asyncio.TimeoutError:
                        await self._terminate(process)
                        stdout, stderr, exit_code = b"", b"", None
                        stdout_truncated = stderr_truncated = False
                        timed_out = True
                    except asyncio.CancelledError:
                        await self._terminate(process)
                        raise
                finally:
                    for task in (stdout_task, stderr_task, wait_task):
                        if not task.done():
                            task.cancel()
            except FileNotFoundError as exc:
                raise RuntimeError("git.command_unavailable") from exc
            except OSError as exc:
                raise RuntimeError("git.command_failed") from exc
        finally:
            if temporary_directory is not None:
                temporary_directory.cleanup()
        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")
        return {
            "command": list(command),
            "exit_code": exit_code,
            "stdout": _redact_text(stdout_text, secret),
            "stderr": _redact_text(stderr_text, secret),
            "_raw_stdout": stdout_text,
            "_raw_stderr": stderr_text,
            "timed_out": timed_out,
            "truncated": stdout_truncated or stderr_truncated,
            "duration_ms": round((time.monotonic() - started) * 1_000),
        }

    async def _scope(self, root: Path) -> Dict[str, str]:
        repository = await self._run(root, ["git", "rev-parse", "--show-toplevel"])
        if repository["timed_out"] or repository["exit_code"] != 0:
            raise ValueError("git.repository_required")
        try:
            actual_root = Path(repository["_raw_stdout"].strip()).resolve(strict=True)
        except (OSError, ValueError) as exc:
            raise ValueError("git.repository_required") from exc
        if actual_root != root:
            raise ValueError("git.root_must_be_repository")

        remote_name = self._remote_name()
        remote = await self._run(root, ["git", "remote", "get-url", remote_name])
        if remote["timed_out"] or remote["exit_code"] != 0:
            raise ValueError("git.remote_missing")

        branch = await self._run(root, ["git", "symbolic-ref", "--quiet", "--short", "HEAD"])
        if branch["timed_out"] or branch["exit_code"] != 0:
            raise ValueError("git.branch_detached")
        current_branch = branch["_raw_stdout"].strip()
        if not current_branch:
            raise ValueError("git.branch_invalid")
        return {"remote": remote_name, "branch": current_branch}

    async def _resolve_secret(
        self,
        context: Dict[str, Any],
    ) -> Tuple[Optional[str], Optional[str]]:
        credential_ref = str(self.config.get("credential_ref", "")).strip()
        if not credential_ref or _SECRET_REF.match(credential_ref):
            return None, "git.credential_ref_invalid"
        port = context.get("_tool_credential_port")
        resolver = getattr(port, "resolve_tool_credential_secret", None)
        tenant_id = context.get("tenant_id")
        if not callable(resolver) or not isinstance(tenant_id, str) or not tenant_id:
            return None, "git.credential_resolver_unavailable"
        try:
            secret = await resolver(tenant_id, credential_ref)
        except asyncio.CancelledError:
            raise
        except Exception:
            return None, "git.credential_unavailable"
        if not isinstance(secret, str) or not secret:
            return None, "git.credential_unavailable"
        return secret, None

    async def _reset_staged(self, root: Path) -> None:
        try:
            await self._run(root, ["git", "reset", "--"])
        except (RuntimeError, ValueError):
            return

    async def _pull_or_push(
        self,
        action: str,
        root: Path,
        scope: Dict[str, str],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        secret, secret_error = await self._resolve_secret(context)
        if secret_error:
            return self._failure(action, secret_error, branch=scope["branch"], remote=scope["remote"])
        if action == "pull":
            command = [
                "git",
                "pull",
                "--no-tags",
                scope["remote"],
                scope["branch"],
            ]
            failure = "git.pull_failed"
        else:
            command = [
                "git",
                "push",
                "--porcelain",
                scope["remote"],
                "HEAD",
            ]
            failure = "git.push_failed"
        try:
            result = await self._run(root, command, secret=secret)
        except RuntimeError:
            return self._failure(action, "git.command_failed", branch=scope["branch"], remote=scope["remote"])
        payload = {
            "action": action,
            "ok": result["exit_code"] == 0 and not result["timed_out"],
            "branch": scope["branch"],
            "remote": scope["remote"],
            **self._public_process(result),
        }
        if not payload["ok"]:
            payload["error"] = "git.pull_timeout" if action == "pull" and result["timed_out"] else (
                "git.push_timeout" if action == "push" and result["timed_out"] else failure
            )
        else:
            payload["pulled" if action == "pull" else "pushed"] = True
        return payload

    @staticmethod
    def _validate_commit_message(value: Any) -> Optional[str]:
        if not isinstance(value, str) or not value.strip() or len(value) > 240:
            return "git.commit_message_invalid"
        if any(ord(char) < 32 for char in value):
            return "git.commit_message_invalid"
        if any(pattern.search(value) for pattern in _SECRET_TEXT_PATTERNS) or _SECRET_REF.match(value.strip()):
            return "git.commit_message_sensitive"
        return None

    async def _commit(
        self,
        root: Path,
        scope: Dict[str, str],
        commit_message: Any,
    ) -> Dict[str, Any]:
        message_error = self._validate_commit_message(commit_message)
        if message_error:
            return self._failure(
                "commit",
                message_error,
                branch=scope["branch"],
                remote=scope["remote"],
            )

        try:
            add_result = await self._run(root, ["git", "add", "--all"])
        except RuntimeError:
            return self._failure("commit", "git.command_failed", branch=scope["branch"], remote=scope["remote"])
        if add_result["exit_code"] != 0 or add_result["timed_out"]:
            return self._failure(
                "commit",
                "git.stage_failed" if not add_result["timed_out"] else "git.stage_timeout",
                branch=scope["branch"],
                remote=scope["remote"],
                **self._public_process(add_result),
            )

        staged_result = await self._run(root, ["git", "diff", "--cached", "--name-only", "-z"])
        if staged_result["exit_code"] != 0 or staged_result["timed_out"]:
            return self._failure(
                "commit",
                "git.stage_inspection_failed",
                branch=scope["branch"],
                remote=scope["remote"],
                **self._public_process(staged_result),
            )
        staged_paths = _parse_nul_names(staged_result["_raw_stdout"])
        if not staged_paths:
            return self._failure(
                "commit",
                "git.nothing_to_commit",
                branch=scope["branch"],
                remote=scope["remote"],
            )

        diff_result = await self._run(
            root,
            ["git", "diff", "--cached", "--no-ext-diff", "--no-color", "--unified=0"],
        )
        if diff_result["exit_code"] != 0 or diff_result["timed_out"]:
            return self._failure(
                "commit",
                "git.diff_failed" if not diff_result["timed_out"] else "git.diff_timeout",
                branch=scope["branch"],
                remote=scope["remote"],
                **self._public_process(diff_result),
            )
        if any(pattern.search(diff_result["_raw_stdout"]) for pattern in _SECRET_TEXT_PATTERNS):
            await self._reset_staged(root)
            return self._failure(
                "commit",
                "git.inline_credential_denied",
                branch=scope["branch"],
                remote=scope["remote"],
            )

        commit_result = await self._run(
            root,
            ["git", "-c", "core.hooksPath=/dev/null", "commit", "-m", str(commit_message)],
        )
        if commit_result["exit_code"] != 0 or commit_result["timed_out"]:
            await self._reset_staged(root)
            return self._failure(
                "commit",
                "git.commit_timeout" if commit_result["timed_out"] else "git.commit_failed",
                branch=scope["branch"],
                remote=scope["remote"],
                **self._public_process(commit_result),
            )
        sha_result = await self._run(root, ["git", "rev-parse", "--verify", "HEAD"])
        commit_sha = sha_result["_raw_stdout"].strip() if sha_result["exit_code"] == 0 else None
        return {
            "action": "commit",
            "ok": True,
            "branch": scope["branch"],
            "remote": scope["remote"],
            "committed": True,
            "commit_sha": commit_sha,
            "files": staged_paths,
            **self._public_process(commit_result),
        }

    async def _commit_and_push(
        self,
        root: Path,
        scope: Dict[str, str],
        context: Dict[str, Any],
        commit_message: Any,
    ) -> Dict[str, Any]:
        commit = await self._commit(root, scope, commit_message)
        if not commit["ok"]:
            commit["action"] = "commit_and_push"
            return commit

        secret, secret_error = await self._resolve_secret(context)
        if secret_error:
            return self._failure(
                "commit_and_push",
                secret_error,
                branch=scope["branch"],
                remote=scope["remote"],
                committed=True,
                commit_sha=commit["commit_sha"],
            )
        try:
            push_result = await self._run(
                root,
                ["git", "push", "--porcelain", scope["remote"], "HEAD"],
                secret=secret,
            )
        except RuntimeError:
            return self._failure(
                "commit_and_push",
                "git.command_failed",
                branch=scope["branch"],
                remote=scope["remote"],
                committed=True,
                commit_sha=commit["commit_sha"],
            )
        payload = {
            "action": "commit_and_push",
            "ok": push_result["exit_code"] == 0 and not push_result["timed_out"],
            "branch": scope["branch"],
            "remote": scope["remote"],
            "committed": True,
            "commit_sha": commit["commit_sha"],
            "files": commit["files"],
            **self._public_process(push_result),
        }
        if payload["ok"]:
            payload["pushed"] = True
        else:
            payload["error"] = "git.push_timeout" if push_result["timed_out"] else "git.push_failed"
        return payload

    async def invoke(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Any:
        action = str(arguments.get("action", "")).strip()
        if action not in _ACTIONS:
            return self._failure(action or "unknown", "git.action_invalid")
        try:
            root = self._root()
            scope = await self._scope(root)
        except asyncio.CancelledError:
            raise
        except (RuntimeError, ValueError) as exc:
            return self._failure(action, str(exc) or "git.scope_invalid")

        if action == "status":
            try:
                result = await self._run(root, ["git", "status", "--short", "--branch"])
            except RuntimeError:
                return self._failure(action, "git.command_failed", **scope)
            payload = {
                "action": action,
                "ok": result["exit_code"] == 0 and not result["timed_out"],
                **scope,
                **self._public_process(result),
            }
            if not payload["ok"]:
                payload["error"] = "git.status_timeout" if result["timed_out"] else "git.status_failed"
            return payload
        if action == "diff":
            try:
                result = await self._run(
                    root,
                    ["git", "diff", "--no-ext-diff", "--no-color", "--unified=20", "--", "."],
                )
            except RuntimeError:
                return self._failure(action, "git.command_failed", **scope)
            payload = {
                "action": action,
                "ok": result["exit_code"] == 0 and not result["timed_out"],
                **scope,
                **self._public_process(result),
            }
            if not payload["ok"]:
                payload["error"] = "git.diff_timeout" if result["timed_out"] else "git.diff_failed"
            return payload
        if action in {"pull", "push"}:
            return await self._pull_or_push(action, root, scope, context)
        if action == "commit":
            return await self._commit(root, scope, arguments.get("commit_message"))
        return await self._commit_and_push(
            root,
            scope,
            context,
            arguments.get("commit_message"),
        )


def create_git_tool(binding: ToolBinding) -> ToolPlugin:
    return GitTool(binding)

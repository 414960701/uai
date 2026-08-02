"""Explicit, bounded local workspace tools for development-only Agents.

This adapter is intentionally not a general shell or a production workspace
service.  The binding supplies the workspace root, while the tool exposes a
small fixed operation set: list/read, Git status/diff, the backend test suite,
and a validated unified patch.  Every subprocess receives a scrubbed
environment and bounded output.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

from .models import PluginKind, PluginManifest, ToolBinding
from .ports import ToolPlugin


WORKSPACE_MANIFEST = PluginManifest(
    id="tool.workspace",
    kind=PluginKind.TOOL,
    display_name="Local workspace",
    version="1.0.0",
    description=(
        "Inspect a bounded local project, review Git changes, run the fixed backend test suite, "
        "and apply a small validated patch. Patch validation rejections return structured "
        "ok=false results. Explicit opt-in for local development only."
    ),
    capabilities=[
        "workspace_read",
        "workspace_write",
        "local_process",
        "bounded_output",
        "auditable",
    ],
    config_schema={
        "type": "object",
        "properties": {
            "root_path": {"type": "string", "minLength": 1, "maxLength": 512},
            "allow_write": {"type": "boolean"},
            "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 600},
            "max_output_bytes": {
                "type": "integer",
                "minimum": 1_024,
                "maximum": 200_000,
            },
            "max_patch_bytes": {
                "type": "integer",
                "minimum": 1_024,
                "maximum": 200_000,
            },
        },
        "required": ["root_path"],
        "additionalProperties": False,
    },
)


ProcessRunner = Callable[..., Awaitable[asyncio.subprocess.Process]]
_ACTIONS = {"list", "read", "git_status", "git_diff", "test", "patch"}
_SENSITIVE_NAMES = {
    ".aws",
    ".docker",
    ".kube",
    ".ssh",
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.test",
    ".git-credentials",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "credentials.json",
    "service-account.json",
    "id_rsa",
    "id_ed25519",
}
_SENSITIVE_SUFFIXES = (".pem", ".p12", ".pfx", ".key")
_REDACT_PATTERNS = (
    re.compile(
        r"(?i)(\b(?:api[_-]?key|authorization|access[_-]?token|refresh[_-]?token|"
        r"password|private[_-]?key|secret)\b\s*[:=]\s*)([^\s,;]+)"
    ),
    re.compile(r"(?i)(\bBearer\s+)([^\s]+)"),
    re.compile(r"\b(?:sk|ghp|github_pat|xoxb|xoxp)-[A-Za-z0-9_-]{12,}\b"),
)


def _redact_text(value: str) -> str:
    result = value or ""
    for pattern in _REDACT_PATTERNS:
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


class WorkspaceTool(ToolPlugin):
    manifest = WORKSPACE_MANIFEST
    name = "workspace"
    description = (
        "Inspect the configured local project, review Git changes, run backend tests, "
        "or apply a small validated patch. Invalid patches return a structured rejection; "
        "do not use for credentials or external side effects."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": sorted(_ACTIONS)},
            "path": {
                "type": "string",
                "maxLength": 512,
                "description": (
                    "Workspace-relative path only (for example backend/src); "
                    "omit path to address the workspace root. Do not use /workspace, "
                    "host absolute paths, or backslashes."
                ),
            },
            "offset": {"type": "integer", "minimum": 0, "maximum": 1_000_000},
            "limit": {"type": "integer", "minimum": 1, "maximum": 400},
            "patch": {"type": "string", "maxLength": 200_000},
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
            raise ValueError("workspace.root_path_must_be_absolute")
        try:
            resolved = root.resolve(strict=True)
        except OSError as exc:
            raise ValueError("workspace.root_path_unavailable") from exc
        if not resolved.is_dir() or resolved == Path("/"):
            raise ValueError("workspace.root_path_invalid")
        return resolved

    @staticmethod
    def _is_sensitive_name(name: str) -> bool:
        lowered = name.lower()
        return (
            lowered in _SENSITIVE_NAMES
            or (lowered.startswith(".env.") and lowered != ".env.example")
            or lowered.endswith(_SENSITIVE_SUFFIXES)
            or lowered.endswith((".sqlite", ".sqlite3", ".db", ".db-wal", ".db-shm"))
        )

    def _relative_path(
        self,
        root: Path,
        value: Any,
        *,
        allow_root: bool = False,
        for_write: bool = False,
    ) -> Tuple[Path, str]:
        raw = str(value or "").strip()
        if not raw:
            if not allow_root:
                raise ValueError("workspace.path_required")
            candidate = root
        else:
            if "\x00" in raw or "\\" in raw or Path(raw).is_absolute():
                raise ValueError("workspace.path_invalid")
            candidate = (root / raw).resolve()
        try:
            relative = candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("workspace.path_outside_root") from exc
        if any(part == ".git" for part in relative.parts):
            raise ValueError("workspace.git_internal_denied")
        if any(self._is_sensitive_name(part) for part in relative.parts):
            raise ValueError("workspace.sensitive_path_denied")
        if for_write and not self.config.get("allow_write", False):
            raise ValueError("workspace.write_disabled")
        return candidate, "." if not relative.parts else relative.as_posix()

    def _list(self, root: Path, value: Any) -> Dict[str, Any]:
        directory, relative = self._relative_path(root, value, allow_root=True)
        if not directory.is_dir():
            raise ValueError("workspace.directory_required")
        entries: List[Dict[str, Any]] = []
        for item in sorted(directory.iterdir(), key=lambda candidate: candidate.name.lower()):
            if item.name == ".git" or self._is_sensitive_name(item.name):
                continue
            try:
                resolved = item.resolve()
                resolved_relative = resolved.relative_to(root)
            except (OSError, ValueError):
                continue
            if any(self._is_sensitive_name(part) for part in resolved_relative.parts):
                continue
            entries.append(
                {
                    "path": (
                        resolved_relative.as_posix()
                        if resolved != root
                        else "."
                    ),
                    "kind": "directory" if item.is_dir() else "file",
                }
            )
            if len(entries) >= 200:
                break
        return {"action": "list", "path": relative, "entries": entries, "truncated": len(entries) >= 200}

    def _read(self, root: Path, arguments: Dict[str, Any]) -> Dict[str, Any]:
        file_path, relative = self._relative_path(root, arguments.get("path"))
        if not file_path.is_file():
            raise ValueError("workspace.file_required")
        max_bytes = _bounded_int(self.config.get("max_output_bytes"), 120_000, 1_024, 200_000)
        offset = _bounded_int(arguments.get("offset"), 0, 0, 1_000_000)
        limit = _bounded_int(arguments.get("limit"), 200, 1, 400)
        selected: List[str] = []
        selected_bytes = 0
        truncated = False
        try:
            with file_path.open("rb") as handle:
                for line_number, raw_line in enumerate(handle):
                    if b"\x00" in raw_line:
                        raise ValueError("workspace.binary_file_denied")
                    if line_number < offset:
                        continue
                    if len(selected) >= limit:
                        truncated = True
                        break
                    try:
                        line = raw_line.decode("utf-8")
                    except UnicodeDecodeError as exc:
                        raise ValueError("workspace.text_file_required") from exc
                    remaining = max_bytes - selected_bytes
                    if remaining <= 0:
                        truncated = True
                        break
                    encoded_size = len(raw_line)
                    if encoded_size > remaining:
                        selected.append(raw_line[:remaining].decode("utf-8", errors="ignore"))
                        truncated = True
                        break
                    selected.append(line)
                    selected_bytes += encoded_size
        except ValueError:
            raise
        except OSError as exc:
            raise ValueError("workspace.read_failed") from exc
        return {
            "action": "read",
            "path": relative,
            "start_line": offset + 1,
            "end_line": offset + len(selected),
            "content": _redact_text("".join(selected)),
            "truncated": truncated,
        }

    async def _collect(
        self,
        process: asyncio.subprocess.Process,
        output_limit: int,
    ) -> Tuple[int, bytes, bytes, bool]:
        stdout_task = asyncio.create_task(_read_limited(process.stdout, output_limit))
        stderr_task = asyncio.create_task(_read_limited(process.stderr, output_limit))
        wait_task = asyncio.create_task(process.wait())
        (stdout, stdout_truncated), (stderr, stderr_truncated), exit_code = await asyncio.gather(
            stdout_task,
            stderr_task,
            wait_task,
        )
        return exit_code, stdout, stderr, stdout_truncated or stderr_truncated

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
        stdin_payload: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        timeout = _bounded_float(self.config.get("timeout_seconds"), 120, 1, 600)
        output_limit = _bounded_int(self.config.get("max_output_bytes"), 120_000, 1_024, 200_000)
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": "/nonexistent",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": str(root / "backend" / "src"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
        started = time.monotonic()
        try:
            process = await self._process_runner(
                *command,
                cwd=str(root),
                env=env,
                stdin=(asyncio.subprocess.PIPE if stdin_payload is not None else asyncio.subprocess.DEVNULL),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            if stdin_payload is not None and process.stdin is not None:
                process.stdin.write(stdin_payload)
                await process.stdin.drain()
                process.stdin.close()
            try:
                exit_code, stdout, stderr, truncated = await asyncio.wait_for(
                    self._collect(process, output_limit),
                    timeout=timeout,
                )
                timed_out = False
            except asyncio.TimeoutError:
                await self._terminate(process)
                exit_code, stdout, stderr, truncated = None, b"", b"", False
                timed_out = True
            except asyncio.CancelledError:
                await self._terminate(process)
                raise
        except FileNotFoundError as exc:
            raise RuntimeError("workspace.command_unavailable") from exc
        duration_ms = round((time.monotonic() - started) * 1_000)
        return {
            "command": list(command),
            "exit_code": exit_code,
            "stdout": _redact_text(stdout.decode("utf-8", errors="replace")),
            "stderr": _redact_text(stderr.decode("utf-8", errors="replace")),
            "timed_out": timed_out,
            "truncated": truncated,
            "duration_ms": duration_ms,
        }

    @staticmethod
    def _patch_paths(patch: str) -> List[str]:
        if not patch.strip():
            raise ValueError("workspace.patch_required")
        if "GIT binary patch" in patch or "new file mode 120000" in patch or "old mode" in patch:
            raise ValueError("workspace.patch_type_denied")
        targets: List[str] = []
        old_path: Optional[str] = None
        for line in patch.splitlines():
            if line.startswith("--- "):
                old_path = line[4:].split("\t", 1)[0].strip()
            elif line.startswith("+++ "):
                new_path = line[4:].split("\t", 1)[0].strip()
                if new_path == "/dev/null":
                    raise ValueError("workspace.patch_delete_denied")
                if old_path is None:
                    raise ValueError("workspace.patch_invalid")
                targets.append(new_path[2:] if new_path.startswith("b/") else new_path)
        if not targets:
            raise ValueError("workspace.patch_invalid")
        return targets

    async def _patch(self, root: Path, patch: str) -> Dict[str, Any]:
        if not self.config.get("allow_write", False):
            raise ValueError("workspace.write_disabled")
        max_patch = _bounded_int(self.config.get("max_patch_bytes"), 120_000, 1_024, 200_000)
        if len(patch.encode("utf-8")) > max_patch:
            raise ValueError("workspace.patch_too_large")
        if re.search(r"(?i)(?:api[_-]?key|authorization|access[_-]?token|password|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=:-]{8,}", patch):
            raise ValueError("workspace.inline_credential_denied")
        targets = self._patch_paths(patch)
        for target in targets:
            self._relative_path(root, target, for_write=True)
        payload = patch.encode("utf-8")
        check = await self._run(
            root,
            ["git", "apply", "--check", "--whitespace=nowarn", "-"],
            stdin_payload=patch.encode("utf-8"),
        )
        if check["timed_out"] or check["exit_code"] != 0:
            raise ValueError("workspace.patch_invalid")
        applied = await self._run(
            root,
            ["git", "apply", "--whitespace=nowarn", "-"],
            stdin_payload=patch.encode("utf-8"),
        )
        if applied["timed_out"] or applied["exit_code"] != 0:
            raise ValueError("workspace.patch_failed")
        return {"action": "patch", "applied": True, "paths": targets}

    async def invoke(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Any:
        del context
        action = str(arguments.get("action", "")).strip()
        if action not in _ACTIONS:
            raise ValueError("workspace.action_invalid")
        root = self._root()
        if action == "list":
            return self._list(root, arguments.get("path"))
        if action == "read":
            return self._read(root, arguments)
        if action == "patch":
            try:
                return {
                    "ok": True,
                    **await self._patch(root, str(arguments.get("patch", ""))),
                }
            except ValueError as exc:
                # A model-generated patch can be syntactically valid JSON but
                # fail the guarded unified-diff checks.  Keep the rejection
                # auditable and model-visible so one malformed patch does not
                # terminate the parent run before it can test or summarize.
                return {
                    "action": "patch",
                    "ok": False,
                    "applied": False,
                    "error": str(exc),
                }
        if action == "git_status":
            result = await self._run(root, ["git", "status", "--short", "--branch"])
            return {"action": action, **result}
        if action == "git_diff":
            command = ["git", "diff", "--no-ext-diff", "--unified=20"]
            if arguments.get("path"):
                _, relative = self._relative_path(root, arguments.get("path"))
                command.extend(["--", relative])
            else:
                command.extend(["--", "."])
            result = await self._run(root, command)
            return {"action": action, **result}
        if action == "test":
            result = await self._run(root, ["python", "-m", "pytest", "backend/tests", "-q"])
            return {"action": action, "suite": "backend", **result}
        raise ValueError("workspace.action_invalid")


def create_workspace_tool(binding: ToolBinding) -> ToolPlugin:
    return WorkspaceTool(binding)

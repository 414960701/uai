"""Process-isolated sandbox adapters.

The core only depends on :class:`SandboxProvider`.  The Docker adapter is an
edge implementation that launches a child container through the Docker CLI;
it never exposes a Docker client object, socket, host mount, or shell to an
Agent.  Other adapters (gVisor, Kata, Firecracker, Wasm, or a remote worker)
can register the same provider contract under their own manifest IDs.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from .models import PluginKind, PluginManifest, SandboxBinding
from .ports import SandboxProvider, SandboxRequest, SandboxResult


SANDBOX_DOCKER_MANIFEST = PluginManifest(
    id="sandbox.docker",
    kind=PluginKind.SANDBOX,
    display_name="Docker child sandbox",
    version="1.0.0",
    description=(
        "Run a bounded non-shell process in a child container with no network, no host mounts, "
        "a read-only root filesystem, dropped capabilities, and resource limits."
    ),
    capabilities=[
        "process_isolation",
        "read_only_rootfs",
        "network_none",
        "resource_limits",
        "oci_runtime",
        "no_host_mounts",
        "concurrency_safe",
    ],
    config_schema={
        "type": "object",
        "properties": {
            "image": {
                "type": "string",
                "minLength": 1,
                "maxLength": 256,
                "pattern": r"^[A-Za-z0-9][A-Za-z0-9./:@_-]{0,255}$",
            },
            "runtime": {
                "type": "string",
                "enum": ["runc", "runsc", "kata-runtime"],
            },
            "memory_mb": {"type": "integer", "minimum": 64, "maximum": 8192},
            "cpus": {"type": "number", "minimum": 0.1, "maximum": 8},
            "pids_limit": {"type": "integer", "minimum": 16, "maximum": 512},
            "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 600},
            "max_output_bytes": {
                "type": "integer",
                "minimum": 1_024,
                "maximum": 2_000_000,
            },
        },
        "required": ["image"],
        "additionalProperties": False,
    },
)


ProcessRunner = Callable[..., Awaitable[asyncio.subprocess.Process]]
_SAFE_IMAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9./:@_-]{0,255}$")
_SAFE_COMMAND_PART = re.compile(r"^[^\x00]*$")


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
            keep = chunk[: limit - seen]
            chunks.append(keep)
        seen += len(chunk)
        if seen > limit:
            truncated = True
    return b"".join(chunks), truncated


class DockerSandbox(SandboxProvider):
    manifest = SANDBOX_DOCKER_MANIFEST

    def __init__(
        self,
        binding: SandboxBinding,
        *,
        process_runner: Optional[ProcessRunner] = None,
    ) -> None:
        self.binding = binding
        self._process_runner = process_runner or asyncio.create_subprocess_exec

    @property
    def config(self) -> Dict[str, Any]:
        return self.binding.config

    def _image(self) -> str:
        image = str(self.config.get("image", "")).strip()
        if not _SAFE_IMAGE.fullmatch(image) or image.startswith("-"):
            raise ValueError("sandbox.docker.image_invalid")
        return image

    def command_for(self, request: SandboxRequest, *, container_name: str) -> List[str]:
        """Build an argv-only Docker command with the non-negotiable hardening flags."""

        if not container_name or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", container_name):
            raise ValueError("sandbox.docker.container_name_invalid")
        if not request.command or any(
            not part or not _SAFE_COMMAND_PART.fullmatch(part) for part in request.command
        ):
            raise ValueError("sandbox.command_invalid")

        runtime = str(self.config.get("runtime", "runc"))
        if runtime not in {"runc", "runsc", "kata-runtime"}:
            raise ValueError("sandbox.docker.runtime_invalid")
        memory_mb = _bounded_int(self.config.get("memory_mb", 512), 512, 64, 8192)
        pids_limit = _bounded_int(self.config.get("pids_limit", 128), 128, 16, 512)
        cpus = _bounded_float(self.config.get("cpus", 1), 1, 0.1, 8)

        command = [
            "docker",
            "run",
            "--rm",
            "--init",
            "--pull=never",
            "--name",
            container_name,
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--pids-limit",
            str(pids_limit),
            "--memory",
            f"{memory_mb}m",
            "--cpus",
            str(cpus),
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--tmpfs",
            "/workspace:rw,noexec,nosuid,size=64m",
            "--user",
            "65532:65532",
            "--workdir",
            "/workspace",
        ]
        if runtime != "runc":
            command.extend(["--runtime", runtime])
        command.extend([self._image(), *request.command])
        return command

    async def _cleanup(self, container_name: str) -> None:
        """Best-effort cleanup after a timeout; never changes the public result."""

        try:
            cleanup = await self._process_runner(
                "docker",
                "rm",
                "-f",
                container_name,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(cleanup.wait(), timeout=5)
        except Exception:
            return

    async def _collect(
        self,
        process: asyncio.subprocess.Process,
        stdin: str,
        output_limit: int,
    ) -> Tuple[int, bytes, bytes, bool]:
        if process.stdin is not None:
            process.stdin.write(stdin.encode("utf-8"))
            await process.stdin.drain()
            process.stdin.close()
        stdout_task = asyncio.create_task(_read_limited(process.stdout, output_limit))
        stderr_task = asyncio.create_task(_read_limited(process.stderr, output_limit))
        wait_task = asyncio.create_task(process.wait())
        (stdout, stdout_truncated), (stderr, stderr_truncated), exit_code = await asyncio.gather(
            stdout_task,
            stderr_task,
            wait_task,
        )
        return exit_code, stdout, stderr, stdout_truncated or stderr_truncated

    async def execute(
        self,
        request: SandboxRequest,
        context: Dict[str, Any],
    ) -> SandboxResult:
        del context
        timeout = _bounded_float(
            request.timeout_seconds or self.config.get("timeout_seconds", 30),
            30,
            1,
            600,
        )
        configured_timeout = self.config.get("timeout_seconds")
        if configured_timeout is not None:
            timeout = min(timeout, _bounded_float(configured_timeout, 30, 1, 600))
        output_limit = _bounded_int(
            request.max_output_bytes or self.config.get("max_output_bytes", 200_000),
            200_000,
            1_024,
            2_000_000,
        )
        configured_output_limit = self.config.get("max_output_bytes")
        if configured_output_limit is not None:
            output_limit = min(
                output_limit,
                _bounded_int(configured_output_limit, 200_000, 1_024, 2_000_000),
            )

        container_name = f"uai-sbx-{uuid4().hex[:24]}"
        command = self.command_for(request, container_name=container_name)
        process = await self._process_runner(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        started = time.monotonic()
        try:
            exit_code, stdout, stderr, truncated = await asyncio.wait_for(
                self._collect(process, request.stdin, output_limit),
                timeout=timeout,
            )
            return SandboxResult(
                exit_code=exit_code,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                truncated=truncated,
                duration_ms=max(0, int((time.monotonic() - started) * 1000)),
            )
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await self._cleanup(container_name)
            return SandboxResult(
                timed_out=True,
                stderr="sandbox execution timed out",
                duration_ms=max(0, int((time.monotonic() - started) * 1000)),
            )
        except asyncio.CancelledError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await self._cleanup(container_name)
            raise


def create_docker_sandbox(binding: SandboxBinding) -> SandboxProvider:
    return DockerSandbox(binding)

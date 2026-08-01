"""Opt-in tool that executes a non-shell command inside a registered sandbox."""

from __future__ import annotations

from typing import Any, Dict

from .models import PluginKind, PluginManifest, SandboxBinding, ToolBinding
from .ports import SandboxRequest, ToolPlugin
from .registry import PluginRegistry


SANDBOX_EXEC_MANIFEST = PluginManifest(
    id="tool.sandbox_exec",
    kind=PluginKind.TOOL,
    display_name="Sandbox command execution",
    version="1.0.0",
    description=(
        "Execute an argv command and optional stdin inside an explicitly configured sandbox. "
        "No shell, host mounts, or credentials are provided."
    ),
    capabilities=["sandboxed_execution", "external_process", "requires_confirmation"],
    config_schema={
        "type": "object",
        "properties": {
            "sandbox_plugin_id": {"type": "string", "minLength": 3, "maxLength": 128},
            "sandbox_config": {"type": "object", "additionalProperties": True},
        },
        "required": ["sandbox_plugin_id"],
        "additionalProperties": False,
    },
)


class SandboxExecTool(ToolPlugin):
    manifest = SANDBOX_EXEC_MANIFEST
    name = "sandbox_exec"
    description = "Execute a non-shell argv command in an explicitly configured sandbox."
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "array",
                "minItems": 1,
                "maxItems": 32,
                "items": {"type": "string", "minLength": 1, "maxLength": 256},
            },
            "stdin": {"type": "string", "maxLength": 1_000_000},
            "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 600},
            "max_output_bytes": {
                "type": "integer",
                "minimum": 1_024,
                "maximum": 2_000_000,
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    }

    def __init__(self, binding: ToolBinding, registry: PluginRegistry) -> None:
        self.binding = binding
        self.registry = registry

    async def invoke(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Any:
        sandbox_plugin_id = str(self.binding.config.get("sandbox_plugin_id", "")).strip()
        if not sandbox_plugin_id:
            raise ValueError("sandbox.plugin_required")
        sandbox = self.registry.create_sandbox(
            SandboxBinding(
                plugin_id=sandbox_plugin_id,
                config=dict(self.binding.config.get("sandbox_config") or {}),
            )
        )
        request = SandboxRequest(
            command=list(arguments.get("command") or []),
            stdin=str(arguments.get("stdin", "")),
            timeout_seconds=arguments.get("timeout_seconds"),
            max_output_bytes=arguments.get("max_output_bytes"),
        )
        result = await sandbox.execute(request, context)
        return result.model_dump()


def create_sandbox_exec(binding: ToolBinding, registry: PluginRegistry) -> ToolPlugin:
    return SandboxExecTool(binding, registry)

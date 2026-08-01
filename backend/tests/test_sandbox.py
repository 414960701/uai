import pytest
from pydantic import ValidationError

from uai_forge.builtins import register_builtins
from uai_forge.models import PluginKind, SandboxBinding, ToolBinding
from uai_forge.ports import SandboxRequest
from uai_forge.registry import PluginRegistry
from uai_forge.sandbox import DockerSandbox
from uai_forge.sandbox_tools import SandboxExecTool


def test_docker_sandbox_command_is_hardened_and_argv_only():
    sandbox = DockerSandbox(
        SandboxBinding(
            plugin_id="sandbox.docker",
            config={
                "image": "python:3.12-alpine",
                "runtime": "runsc",
                "memory_mb": 256,
                "pids_limit": 64,
            },
        )
    )
    request = SandboxRequest(command=["python", "-c", "print('ok')"])

    command = sandbox.command_for(request, container_name="uai-sbx-test")

    assert command[:3] == ["docker", "run", "--rm"]
    assert "--pull=never" in command
    assert "--network=none" in command
    assert "--read-only" in command
    assert "--cap-drop=ALL" in command
    assert "--security-opt=no-new-privileges:true" in command
    assert "--runtime" in command
    assert command[command.index("--runtime") + 1] == "runsc"
    assert "--privileged" not in command
    assert "--cap-add" not in command
    assert any(value.startswith("/workspace:rw") for value in command)
    assert command[-3:] == ["python", "-c", "print('ok')"]


def test_sandbox_request_rejects_empty_or_nul_command_parts():
    with pytest.raises(ValidationError):
        SandboxRequest(command=[])

    with pytest.raises(ValidationError):
        SandboxRequest(command=["python\x00"])


def test_sandbox_provider_is_extensible_through_the_registry():
    registry = PluginRegistry()
    register_builtins(registry)

    manifest = registry.manifest("sandbox.docker", PluginKind.SANDBOX)
    assert manifest is not None
    sandbox = registry.create_sandbox(
        SandboxBinding(
            plugin_id="sandbox.docker",
            config={"image": "python:3.12-alpine"},
        )
    )
    assert isinstance(sandbox, DockerSandbox)


def test_sandbox_exec_is_opt_in_and_requires_a_provider_binding():
    registry = PluginRegistry()
    register_builtins(registry)

    with pytest.raises(ValueError, match="plugin.config_invalid"):
        registry.create_tool(ToolBinding(plugin_id="tool.sandbox_exec"))

    tool = registry.create_tool(
        ToolBinding(
            plugin_id="tool.sandbox_exec",
            permission="confirm",
            config={
                "sandbox_plugin_id": "sandbox.docker",
                "sandbox_config": {"image": "alpine:3.20"},
            },
        )
    )
    assert isinstance(tool, SandboxExecTool)

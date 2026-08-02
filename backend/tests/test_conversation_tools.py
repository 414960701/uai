import json

import pytest

from uai_forge.builtins import register_builtins
from uai_forge.conversation_tools import ConversationTool
from uai_forge.models import PluginKind, RunRecord, ToolBinding
from uai_forge.ports import RunSubmissionPort
from uai_forge.registry import PluginRegistry


class SubmissionPort:
    def __init__(self):
        self.calls = []

    async def start(self, tenant_id, request):
        self.calls.append((tenant_id, request))
        return RunRecord(
            id="run_follow_up",
            tenant_id=tenant_id,
            agent_id=request.agent_id,
            agent_revision=request.agent_revision or 7,
            session_id=request.session_id,
            input=request.input,
        )


def test_conversation_manifest_is_registered_and_uses_owned_contract():
    registry = PluginRegistry()
    register_builtins(registry)

    manifest = registry.manifest("tool.conversation", PluginKind.TOOL)
    assert manifest is not None
    assert "run_submission" in manifest.capabilities
    assert isinstance(
        registry.create_tool(ToolBinding(plugin_id="tool.conversation")),
        ConversationTool,
    )
    assert isinstance(SubmissionPort(), RunSubmissionPort)


@pytest.mark.asyncio
async def test_conversation_starts_new_session_for_current_agent():
    port = SubmissionPort()
    tool = ConversationTool(ToolBinding(plugin_id="tool.conversation"))

    result = await tool.invoke(
        {"input": "继续检查当前框架并实现下一项能力"},
        {
            "tenant_id": "default",
            "run_id": "run_parent",
            "agent_id": "agt_evolution",
            "_run_submission_port": port,
        },
    )

    assert result["ok"] is True
    assert result["run_id"] == "run_follow_up"
    assert result["agent_id"] == "agt_evolution"
    assert result["session_id"].startswith("ses_")
    assert len(port.calls) == 1
    tenant, request = port.calls[0]
    assert tenant == "default"
    assert request.agent_id == "agt_evolution"
    assert request.session_id == result["session_id"]
    assert request.metadata["parent_run_id"] == "run_parent"
    assert request.metadata["source"] == "tool.conversation"


@pytest.mark.asyncio
async def test_conversation_accepts_explicit_target_and_mode_without_secret_output():
    port = SubmissionPort()
    tool = ConversationTool(ToolBinding(plugin_id="tool.conversation"))

    result = await tool.invoke(
        {
            "input": "继续处理下一阶段",
            "agent_id": "agt_other",
            "agent_revision": 3,
            "session_id": "ses_next",
            "thinking_mode": "off",
            "execution_mode": "execute",
            "metadata": {"stage": "implementation"},
        },
        {
            "tenant_id": "tenant_a",
            "run_id": "run_parent",
            "agent_id": "agt_evolution",
            "_run_submission_port": port,
        },
    )

    assert result["ok"] is True
    assert result["session_id"] == "ses_next"
    assert port.calls[0][1].agent_id == "agt_other"
    assert port.calls[0][1].agent_revision == 3
    assert port.calls[0][1].execution_mode.value == "execute"
    assert "tenant_a" not in json.dumps(result)


@pytest.mark.asyncio
async def test_conversation_fails_closed_without_run_submission_port():
    tool = ConversationTool(ToolBinding(plugin_id="tool.conversation"))

    result = await tool.invoke(
        {"input": "继续"},
        {"tenant_id": "default", "agent_id": "agt_evolution"},
    )

    assert result == {
        "ok": False,
        "action": "start",
        "error": "conversation.run_submission_unavailable",
    }


@pytest.mark.asyncio
async def test_conversation_rejects_inline_secret_metadata():
    port = SubmissionPort()
    tool = ConversationTool(ToolBinding(plugin_id="tool.conversation"))

    result = await tool.invoke(
        {
            "input": "继续",
            "metadata": {"token": "fixture-secret"},
        },
        {
            "tenant_id": "default",
            "agent_id": "agt_evolution",
            "_run_submission_port": port,
        },
    )

    assert result["ok"] is False
    assert result["error"] == "conversation.request_invalid"
    assert not port.calls

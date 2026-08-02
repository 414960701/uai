"""A first-party tool for starting a follow-up Agent conversation.

The tool submits a normal UAI Forge ``RunRequest`` through the application
port.  It does not call HTTP, access storage directly, or bypass the regular
topology, revision, session and policy checks performed by ``RunManager``.
"""

from __future__ import annotations

from typing import Any, Dict

from .models import ExecutionMode, PluginKind, PluginManifest, RunRequest, ThinkingMode, ToolBinding, new_id
from .ports import RunSubmissionPort, ToolPlugin


CONVERSATION_MANIFEST = PluginManifest(
    id="tool.conversation",
    kind=PluginKind.TOOL,
    display_name="Start conversation",
    version="1.0.0",
    description=(
        "Start a new UAI Forge Agent conversation through the normal RunManager. "
        "The follow-up receives its own session and continues from the supplied task input."
    ),
    capabilities=["conversation_start", "run_submission", "async_follow_up", "auditable"],
    config_schema={
        "type": "object",
        "additionalProperties": False,
    },
)


class ConversationTool(ToolPlugin):
    manifest = CONVERSATION_MANIFEST
    name = "conversation"
    description = (
        "Start a new Agent conversation for a follow-up task. Omit agent_id to continue the "
        "current Agent; omit session_id to create a new conversation session."
    )
    parameters = {
        "type": "object",
        "properties": {
            "input": {
                "type": "string",
                "minLength": 1,
                "maxLength": 100_000,
                "description": "The next conversation's task input.",
            },
            "agent_id": {"type": "string", "minLength": 1, "maxLength": 120},
            "agent_revision": {"type": "integer", "minimum": 1},
            "session_id": {"type": "string", "minLength": 1, "maxLength": 120},
            "thinking_mode": {
                "type": "string",
                "enum": [mode.value for mode in ThinkingMode],
            },
            "execution_mode": {
                "type": "string",
                "enum": [mode.value for mode in ExecutionMode],
            },
            "metadata": {
                "type": "object",
                "additionalProperties": True,
            },
        },
        "required": ["input"],
        "additionalProperties": False,
    }

    def __init__(self, binding: ToolBinding) -> None:
        self.binding = binding

    @staticmethod
    def _failure(error: str) -> Dict[str, Any]:
        return {"ok": False, "action": "start", "error": error}

    async def invoke(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Any:
        port = context.get("_run_submission_port")
        if not isinstance(port, RunSubmissionPort):
            return self._failure("conversation.run_submission_unavailable")

        input_text = arguments.get("input")
        if not isinstance(input_text, str) or not input_text.strip():
            return self._failure("conversation.input_required")
        agent_id = arguments.get("agent_id") or context.get("agent_id")
        if not isinstance(agent_id, str) or not agent_id:
            return self._failure("conversation.agent_required")
        session_id = arguments.get("session_id") or new_id("ses")
        if not isinstance(session_id, str) or not session_id:
            return self._failure("conversation.session_invalid")

        try:
            request = RunRequest(
                agent_id=agent_id,
                agent_revision=arguments.get("agent_revision"),
                input=input_text,
                session_id=session_id,
                thinking_mode=arguments.get("thinking_mode", ThinkingMode.AUTO),
                execution_mode=arguments.get("execution_mode", ExecutionMode.EXECUTE),
                metadata={
                    "parent_run_id": context.get("run_id"),
                    "parent_agent_id": context.get("agent_id"),
                    "source": "tool.conversation",
                    **(arguments.get("metadata") or {}),
                },
            )
        except Exception:
            return self._failure("conversation.request_invalid")

        tenant_id = context.get("tenant_id")
        if not isinstance(tenant_id, str) or not tenant_id:
            return self._failure("conversation.tenant_unavailable")
        try:
            run = await port.start(tenant_id, request)
        except LookupError:
            return self._failure("conversation.agent_not_found")
        except ValueError:
            return self._failure("conversation.start_rejected")
        except Exception:
            return self._failure("conversation.start_failed")
        return {
            "ok": True,
            "action": "start",
            "run_id": run.id,
            "agent_id": run.agent_id,
            "agent_revision": run.agent_revision,
            "session_id": run.session_id,
            "status": run.status.value,
            "parent_run_id": context.get("run_id"),
        }


def create_conversation_tool(binding: ToolBinding) -> ToolPlugin:
    return ConversationTool(binding)

"""Registration of first-party adapters."""

from __future__ import annotations

from .memory import IN_PROCESS_MEMORY_MANIFEST, create_in_process_memory
from .middleware import AUDIT_MIDDLEWARE_MANIFEST, create_audit_tags
from .models import PluginKind, PluginManifest
from .providers import (
    ANTHROPIC_MESSAGES_MANIFEST,
    OPENAI_COMPATIBLE_MANIFEST,
    create_anthropic_messages_provider,
    create_openai_compatible_provider,
)
from .registry import PluginRegistry
from .sandbox import SANDBOX_DOCKER_MANIFEST, create_docker_sandbox
from .sandbox_tools import SANDBOX_EXEC_MANIFEST, create_sandbox_exec
from .tools import (
    CALCULATOR_MANIFEST,
    ECHO_MANIFEST,
    UTC_NOW_MANIFEST,
    create_calculator,
    create_echo,
    create_utc_now,
)
from .git_tools import GIT_MANIFEST, create_git_tool
from .conversation_tools import CONVERSATION_MANIFEST, create_conversation_tool
from .web_tools import (
    WEB_FETCH_MANIFEST,
    WEB_JSON_MANIFEST,
    WEB_RSS_MANIFEST,
    WEB_SEARCH_MANIFEST,
    create_web_fetch,
    create_web_json,
    create_web_rss,
    create_web_search,
)
from .workspace_tools import WORKSPACE_MANIFEST, create_workspace_tool


def register_builtins(registry: PluginRegistry) -> None:
    registry.register_provider(OPENAI_COMPATIBLE_MANIFEST, create_openai_compatible_provider)
    registry.register_provider(ANTHROPIC_MESSAGES_MANIFEST, create_anthropic_messages_provider)
    registry.register_tool(CALCULATOR_MANIFEST, create_calculator)
    registry.register_tool(ECHO_MANIFEST, create_echo)
    registry.register_tool(UTC_NOW_MANIFEST, create_utc_now)
    registry.register_tool(GIT_MANIFEST, create_git_tool)
    registry.register_tool(CONVERSATION_MANIFEST, create_conversation_tool)
    registry.register_tool(WEB_SEARCH_MANIFEST, create_web_search)
    registry.register_tool(WEB_FETCH_MANIFEST, create_web_fetch)
    registry.register_tool(WEB_JSON_MANIFEST, create_web_json)
    registry.register_tool(WEB_RSS_MANIFEST, create_web_rss)
    registry.register_sandbox(SANDBOX_DOCKER_MANIFEST, create_docker_sandbox)
    registry.register_tool(
        SANDBOX_EXEC_MANIFEST,
        lambda binding: create_sandbox_exec(binding, registry),
    )
    registry.register_tool(WORKSPACE_MANIFEST, create_workspace_tool)
    registry.register_memory(IN_PROCESS_MEMORY_MANIFEST, create_in_process_memory)
    registry.register_middleware(AUDIT_MIDDLEWARE_MANIFEST, create_audit_tags)
    registry.register_manifest(
        PluginManifest(
            id="storage.sqlite",
            kind=PluginKind.STORAGE,
            display_name="SQLite control-plane storage",
            version="1.0.0",
            description="Single-node durable storage with revision and event history.",
            capabilities=["transactions", "revision_history", "event_replay", "local"],
        )
    )
    registry.register_manifest(
        PluginManifest(
            id="event_bus.in_process",
            kind=PluginKind.EVENT_BUS,
            display_name="In-process event broker",
            version="1.0.0",
            description="Durable SQLite replay plus live per-run asyncio fan-out.",
            capabilities=["replay", "sse", "ordered_per_run", "single_process"],
        )
    )
    registry.register_manifest(
        PluginManifest(
            id="scheduler.local",
            kind=PluginKind.SCHEDULER,
            display_name="Local asyncio scheduler",
            version="0.1.0",
            description="Capability placeholder for the scheduler extension contract.",
            capabilities=["run_submission"],
            available=False,
        )
    )
    registry.register_manifest(
        PluginManifest(
            id="ui.control_center",
            kind=PluginKind.UI,
            display_name="UAI Forge Control Center",
            version="1.0.0",
            description="Schema-oriented configuration and run observability console.",
            capabilities=["agent_editor", "topology", "event_timeline", "plugin_catalog"],
        )
    )

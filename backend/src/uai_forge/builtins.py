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
from .tools import (
    CALCULATOR_MANIFEST,
    ECHO_MANIFEST,
    UTC_NOW_MANIFEST,
    create_calculator,
    create_echo,
    create_utc_now,
)


def register_builtins(registry: PluginRegistry) -> None:
    registry.register_provider(OPENAI_COMPATIBLE_MANIFEST, create_openai_compatible_provider)
    registry.register_provider(ANTHROPIC_MESSAGES_MANIFEST, create_anthropic_messages_provider)
    registry.register_tool(CALCULATOR_MANIFEST, create_calculator)
    registry.register_tool(ECHO_MANIFEST, create_echo)
    registry.register_tool(UTC_NOW_MANIFEST, create_utc_now)
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

from uuid import uuid4

import pytest

from uai_forge.builtins import register_builtins
from uai_forge.events import EventBroker
from uai_forge.graph import AgentGraphValidator
from uai_forge.memory import create_in_process_memory
from uai_forge.models import (
    AgentSpec,
    MemoryBinding,
    PluginKind,
    PluginManifest,
    RunRequest,
    RunStatus,
)
from uai_forge.ports import ModelMessage
from uai_forge.registry import PluginRegistry
from uai_forge.run_manager import RunManager
from uai_forge.runtime import AgentRuntime
from uai_forge.storage import SQLiteRepository


@pytest.mark.asyncio
async def test_disabled_memory_binding_never_creates_loads_or_appends(tmp_path):
    repository = SQLiteRepository(str(tmp_path / "disabled-memory.db"))
    await repository.initialize()
    registry = PluginRegistry()
    register_builtins(registry)
    calls = {"create": 0, "load": 0, "append": 0}

    class RecordingMemory:
        async def load(self, tenant_id, session_id, agent_id):
            calls["load"] += 1
            return []

        async def append(self, tenant_id, session_id, agent_id, messages):
            calls["append"] += 1

    def create_recording_memory(binding):
        calls["create"] += 1
        return RecordingMemory()

    registry.register_memory(
        PluginManifest(
            id="memory.recording",
            kind=PluginKind.MEMORY,
            display_name="Recording memory",
            source="entry_point",
            config_schema={
                "type": "object",
                "additionalProperties": False,
            },
        ),
        create_recording_memory,
    )
    agent = await repository.save_agent(
        "default",
        AgentSpec(
            id="agt_disabled_memory",
            name="Disabled Memory",
            system_prompt="Return without touching memory.",
            memory=MemoryBinding(
                plugin_id="memory.recording",
                enabled=False,
            ),
        ),
    )
    events = EventBroker(repository)
    runtime = AgentRuntime(repository, registry, events)
    manager = RunManager(
        repository,
        runtime,
        events,
        AgentGraphValidator(repository),
    )

    run = await manager.start(
        "default",
        RunRequest(agent_id=agent.id, input="memory must stay disabled"),
    )
    finished = await manager.wait("default", run.id)

    assert finished.status == RunStatus.SUCCEEDED
    assert calls == {"create": 0, "load": 0, "append": 0}


@pytest.mark.asyncio
async def test_in_process_memory_applies_retention_per_binding_without_cross_agent_leak():
    suffix = uuid4().hex
    small = create_in_process_memory(
        MemoryBinding(config={"max_messages": 2})
    )
    large = create_in_process_memory(
        MemoryBinding(config={"max_messages": 5})
    )
    messages = [
        ModelMessage(role="user", content=f"message-{index}")
        for index in range(5)
    ]

    await small.append("default", suffix, f"agt_small_{suffix}", messages)
    await large.append("default", suffix, f"agt_large_{suffix}", messages)

    small_items = await small.load(
        "default",
        suffix,
        f"agt_small_{suffix}",
    )
    large_items = await large.load(
        "default",
        suffix,
        f"agt_large_{suffix}",
    )

    assert small is not large
    assert [item.content for item in small_items] == ["message-3", "message-4"]
    assert [item.content for item in large_items] == [
        "message-0",
        "message-1",
        "message-2",
        "message-3",
        "message-4",
    ]

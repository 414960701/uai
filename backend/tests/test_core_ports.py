from typing import Dict, Optional, Tuple, get_type_hints

import pytest

from uai_forge.builtins import register_builtins
from uai_forge.events import EventBroker
from uai_forge.graph import AgentGraphValidator
from uai_forge.models import (
    AgentInstance,
    AgentSpec,
    EventType,
    ModelConfig,
    RunEvent,
    RunRecord,
    RunRequest,
    RunStatus,
)
from uai_forge.ports import (
    ConfigurationPort,
    EventBusPort,
    EventStorePort,
    EventStreamPort,
    RepositoryPort,
)
from uai_forge.registry import PluginRegistry
from uai_forge.run_manager import RunManager
from uai_forge.runtime import AgentRuntime
from uai_forge.storage import SQLiteRepository
from test_support import register_test_provider


class InMemoryCoreRepository:
    """A deliberately small non-SQLite structural implementation."""

    def __init__(self, agents: list[AgentSpec]) -> None:
        self._agents: Dict[Tuple[str, str, int], AgentSpec] = {
            (agent.tenant_id, agent.id, agent.revision): agent for agent in agents
        }
        self._latest: Dict[Tuple[str, str], AgentSpec] = {
            (agent.tenant_id, agent.id): agent for agent in agents
        }
        self._instances: Dict[Tuple[str, str], AgentInstance] = {}
        self._runs: Dict[Tuple[str, str], RunRecord] = {}
        self._configs = {
            (agent.tenant_id, agent.model.model_config_id): ModelConfig(
                id=agent.model.model_config_id,
                tenant_id=agent.tenant_id,
                name="Portable test connection",
                provider="test.deterministic",
                protocol="test",
                model="deterministic",
            )
            for agent in agents
        }

    async def get_agent(
        self,
        tenant_id: str,
        agent_id: str,
        revision: Optional[int] = None,
    ) -> Optional[AgentSpec]:
        if revision is None:
            return self._latest.get((tenant_id, agent_id))
        return self._agents.get((tenant_id, agent_id, revision))

    async def get_instance(
        self,
        tenant_id: str,
        instance_id: str,
    ) -> Optional[AgentInstance]:
        return self._instances.get((tenant_id, instance_id))

    async def create_run(self, run: RunRecord) -> RunRecord:
        self._runs[(run.tenant_id, run.id)] = run
        return run

    async def update_run(self, run: RunRecord) -> RunRecord:
        self._runs[(run.tenant_id, run.id)] = run
        return run

    async def get_run(self, tenant_id: str, run_id: str) -> Optional[RunRecord]:
        return self._runs.get((tenant_id, run_id))

    async def get_model_config(self, tenant_id: str, config_id: str):
        return self._configs.get((tenant_id, config_id))

    async def resolve_model_config_secret(self, tenant_id: str, config_id: str):
        return "test-only-secret"


class RecordingEventBus:
    def __init__(self) -> None:
        self.events: list[RunEvent] = []
        self._sequences: Dict[Tuple[str, str], int] = {}

    async def publish(self, tenant_id: str, event: RunEvent) -> RunEvent:
        key = (tenant_id, event.run_id)
        sequence = self._sequences.get(key, 0) + 1
        self._sequences[key] = sequence
        saved = event.model_copy(update={"sequence": sequence})
        self.events.append(saved)
        return saved


@pytest.mark.asyncio
async def test_execution_core_accepts_non_sqlite_repository_and_event_bus_ports():
    agent = AgentSpec(
        id="agt_portable_core",
        name="Portable Core",
        system_prompt="Return a deterministic answer.",
    )
    repository = InMemoryCoreRepository([agent])
    event_bus = RecordingEventBus()
    registry = PluginRegistry()
    register_builtins(registry)
    register_test_provider(registry)
    register_test_provider(registry, "openai_compatible")

    assert isinstance(repository, RepositoryPort)
    assert isinstance(event_bus, EventBusPort)

    validator = AgentGraphValidator(repository)
    runtime = AgentRuntime(repository, registry, event_bus)
    manager = RunManager(repository, runtime, event_bus, validator)

    run = await manager.start(
        "default",
        RunRequest(agent_id=agent.id, input="verify the structural ports"),
    )
    finished = await manager.wait("default", run.id)

    assert finished is not None
    assert finished.status == RunStatus.SUCCEEDED
    assert "verify the structural ports" in (finished.output or "")
    assert event_bus.events[0].type == EventType.RUN_STARTED
    assert event_bus.events[-1].type == EventType.RUN_COMPLETED


def test_execution_core_constructor_annotations_use_owned_ports():
    assert get_type_hints(AgentGraphValidator.__init__)["repository"] is RepositoryPort
    assert get_type_hints(AgentRuntime.__init__)["repository"] is RepositoryPort
    assert get_type_hints(AgentRuntime.__init__)["event_broker"] is EventBusPort
    assert get_type_hints(RunManager.__init__)["repository"] is RepositoryPort
    assert get_type_hints(RunManager.__init__)["events"] is EventBusPort


def test_builtin_local_adapters_structurally_implement_owned_ports(tmp_path):
    repository = SQLiteRepository(str(tmp_path / "structural-adapter.db"))
    event_bus = EventBroker(repository)

    assert isinstance(repository, RepositoryPort)
    assert isinstance(repository, ConfigurationPort)
    assert isinstance(repository, EventStorePort)
    assert isinstance(event_bus, EventBusPort)
    assert isinstance(event_bus, EventStreamPort)

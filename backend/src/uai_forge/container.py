"""Application composition root."""

from __future__ import annotations

from dataclasses import dataclass

from .builtins import register_builtins
from .events import EventBroker
from .graph import AgentGraphValidator
from .registry import PluginRegistry
from .run_manager import RunManager
from .runtime import AgentRuntime
from .settings import Settings
from .storage import SQLiteRepository
from .validated_repository import ValidatedAgentRepository


@dataclass
class Container:
    settings: Settings
    repository: ValidatedAgentRepository
    registry: PluginRegistry
    events: EventBroker
    validator: AgentGraphValidator
    runtime: AgentRuntime
    runs: RunManager

    @classmethod
    def build(cls, settings: Settings) -> "Container":
        storage = SQLiteRepository(settings.database_path)
        registry = PluginRegistry()
        register_builtins(registry)
        registry.discover_entry_points()
        repository = ValidatedAgentRepository(storage, registry)
        events = EventBroker(storage)
        validator = AgentGraphValidator(repository)
        runtime = AgentRuntime(repository, registry, events)
        runs = RunManager(repository, runtime, events, validator)
        return cls(
            settings=settings,
            repository=repository,
            registry=registry,
            events=events,
            validator=validator,
            runtime=runtime,
            runs=runs,
        )

"""Application persistence boundary that validates plugin-bound Agent specs."""

from __future__ import annotations

from typing import Any, Optional

from .models import AgentSpec
from .registry import PluginRegistry


class ValidatedAgentRepository:
    """Decorate a control repository without coupling storage to plugin loading.

    Administrative methods not involved in Agent writes are delegated as-is.
    This keeps SQLite replaceable while ensuring every composed application
    validates a definition before it becomes a persisted revision.
    """

    def __init__(self, delegate: Any, registry: PluginRegistry) -> None:
        self._delegate = delegate
        self._registry = registry

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    async def save_agent(
        self,
        tenant_id: str,
        spec: AgentSpec,
        expected_revision: Optional[int] = None,
    ) -> AgentSpec:
        self._registry.validate_agent_spec(spec)
        return await self._delegate.save_agent(
            tenant_id,
            spec,
            expected_revision=expected_revision,
        )

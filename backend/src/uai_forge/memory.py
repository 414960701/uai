"""Built-in memory adapters."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import DefaultDict, List, Tuple

from .models import MemoryBinding, PluginKind, PluginManifest
from .ports import MemoryStore, ModelMessage


IN_PROCESS_MEMORY_MANIFEST = PluginManifest(
    id="memory.in_process",
    kind=PluginKind.MEMORY,
    display_name="In-process session memory",
    version="1.0.0",
    description="Bounded short-term memory for local development and tests.",
    capabilities=["session_scoped", "bounded", "ephemeral"],
    config_schema={
        "type": "object",
        "properties": {"max_messages": {"type": "integer", "minimum": 2, "maximum": 500}},
        "additionalProperties": False,
    },
)


class InProcessMemory(MemoryStore):
    manifest = IN_PROCESS_MEMORY_MANIFEST

    def __init__(
        self,
        binding: MemoryBinding,
        backend: "_InProcessMemoryBackend" = None,
    ) -> None:
        self.max_messages = int(binding.config.get("max_messages", 40))
        self._backend = backend or _shared_memory_backend

    async def load(self, tenant_id: str, session_id: str, agent_id: str) -> List[ModelMessage]:
        key = (tenant_id, session_id, agent_id)
        async with self._backend.lock:
            return [
                item.model_copy(deep=True)
                for item in self._backend.items[key][-self.max_messages :]
            ]

    async def append(
        self,
        tenant_id: str,
        session_id: str,
        agent_id: str,
        messages: List[ModelMessage],
    ) -> None:
        key = (tenant_id, session_id, agent_id)
        async with self._backend.lock:
            self._backend.items[key].extend(
                item.model_copy(deep=True) for item in messages
            )
            self._backend.items[key] = self._backend.items[key][
                -self.max_messages :
            ]


class _InProcessMemoryBackend:
    """Shared process-local data; retention remains binding-local."""

    def __init__(self) -> None:
        self.items: DefaultDict[
            Tuple[str, str, str],
            List[ModelMessage],
        ] = defaultdict(list)
        self.lock = asyncio.Lock()


_shared_memory_backend = _InProcessMemoryBackend()


def create_in_process_memory(binding: MemoryBinding) -> MemoryStore:
    # Each binding gets its own policy view while data remains session-continuous.
    return InProcessMemory(binding, _shared_memory_backend)

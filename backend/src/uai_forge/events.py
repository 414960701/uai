"""Durable event append plus live fan-out."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import AsyncIterator, DefaultDict, Optional, Set, Tuple, Union, cast

from .models import EventType, RunEvent
from .ports import EventStorePort

TERMINAL_EVENTS = {
    EventType.RUN_COMPLETED,
    EventType.RUN_FAILED,
    EventType.RUN_CANCELLED,
}


class _DisconnectSignal:
    """Internal marker that closes a live stream so it can resume from storage."""


_DISCONNECT = _DisconnectSignal()
_QueueItem = Union[RunEvent, _DisconnectSignal]


class EventBroker:
    def __init__(
        self,
        repository: EventStorePort,
        subscriber_queue_size: int = 1_000,
    ) -> None:
        if subscriber_queue_size < 1:
            raise ValueError("subscriber_queue_size must be at least one")
        self.repository = repository
        self._subscribers: DefaultDict[
            Tuple[str, str], Set[asyncio.Queue[_QueueItem]]
        ] = defaultdict(set)
        self._subscriber_queue_size = subscriber_queue_size
        self._lock = asyncio.Lock()

    async def publish(self, tenant_id: str, event: RunEvent) -> RunEvent:
        saved = await self.repository.append_event(tenant_id, event)
        key = (tenant_id, event.run_id)
        async with self._lock:
            subscribers = self._subscribers.get(key)
            if not subscribers:
                return saved
            for queue in tuple(subscribers):
                try:
                    queue.put_nowait(saved)
                except asyncio.QueueFull:
                    # Persistence already succeeded. Isolate the slow subscriber
                    # instead of turning backpressure into a failed Run. Clearing
                    # queued live events is safe because the client resumes from
                    # its last delivered durable sequence after this stream closes.
                    subscribers.discard(queue)
                    while True:
                        try:
                            queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                    queue.put_nowait(_DISCONNECT)
            if not subscribers:
                self._subscribers.pop(key, None)
        return saved

    async def subscribe(
        self,
        tenant_id: str,
        run_id: str,
        after_sequence: int = 0,
        heartbeat_seconds: float = 15.0,
    ) -> AsyncIterator[Optional[RunEvent]]:
        key = (tenant_id, run_id)
        queue: asyncio.Queue[_QueueItem] = asyncio.Queue(
            maxsize=self._subscriber_queue_size
        )
        async with self._lock:
            self._subscribers[key].add(queue)
        last_sequence = after_sequence
        try:
            replay = await self.repository.list_events(tenant_id, run_id, after_sequence)
            for event in replay:
                if event.sequence <= last_sequence:
                    continue
                last_sequence = event.sequence
                yield event
                if event.type in TERMINAL_EVENTS:
                    return
            while True:
                try:
                    item = await asyncio.wait_for(
                        queue.get(), timeout=heartbeat_seconds
                    )
                except asyncio.TimeoutError:
                    if await self.repository.terminal_event_exists(tenant_id, run_id):
                        replay = await self.repository.list_events(
                            tenant_id, run_id, last_sequence
                        )
                        for item in replay:
                            last_sequence = item.sequence
                            yield item
                        return
                    yield None
                    continue
                if item is _DISCONNECT:
                    return
                event = cast(RunEvent, item)
                if event.sequence <= last_sequence:
                    continue
                last_sequence = event.sequence
                yield event
                if event.type in TERMINAL_EVENTS:
                    return
        finally:
            async with self._lock:
                subscribers = self._subscribers.get(key)
                if subscribers is not None:
                    subscribers.discard(queue)
                    if not subscribers:
                        self._subscribers.pop(key, None)

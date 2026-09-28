"""进程内事件总线：协作实时广播（peer_turn 等）。"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class BusEvent:
    session_id: str
    event: str
    data: dict[str, Any]


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue[BusEvent]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, session_id: str) -> asyncio.Queue[BusEvent]:
        queue: asyncio.Queue[BusEvent] = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subs[session_id].append(queue)
        return queue

    async def unsubscribe(
        self, session_id: str, queue: asyncio.Queue[BusEvent]
    ) -> None:
        async with self._lock:
            try:
                self._subs[session_id].remove(queue)
            except ValueError:
                pass

    async def publish(self, event: BusEvent) -> None:
        async with self._lock:
            targets = list(self._subs.get(event.session_id, []))
        for queue in targets:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def stream(self, session_id: str) -> AsyncIterator[BusEvent]:
        queue = await self.subscribe(session_id)
        try:
            while True:
                yield await queue.get()
        finally:
            await self.unsubscribe(session_id, queue)


_bus: EventBus | None = None
_bus_lock = asyncio.Lock()


async def get_bus() -> EventBus:
    global _bus
    if _bus is None:
        async with _bus_lock:
            if _bus is None:
                _bus = EventBus()
    return _bus

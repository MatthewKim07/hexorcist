"""Per-run event bus. Every event is persisted first, so a late subscriber can replay the run."""
from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator

from .store import Store


class RunBus:
    def __init__(self, run_id: str, store: Store) -> None:
        self.run_id = run_id
        self.store = store
        self.seq = 0
        self.closed = False
        self._changed = asyncio.Condition()

    async def emit(self, type_: str, **data) -> None:
        self.seq += 1
        event = {"seq": self.seq, "type": type_, "t": time.time(), **data}
        await asyncio.to_thread(self.store.add_event, self.run_id, self.seq, event)
        async with self._changed:
            self._changed.notify_all()

    async def step(self, step: str, status: str, detail: str = "", **data) -> None:
        await self.emit("step", step=step, status=status, detail=detail, **data)

    async def close(self) -> None:
        self.closed = True
        async with self._changed:
            self._changed.notify_all()

    async def wait_for_change(self, timeout: float) -> None:
        async with self._changed:
            try:
                await asyncio.wait_for(self._changed.wait(), timeout)
            except asyncio.TimeoutError:
                pass


class BusRegistry:
    def __init__(self, store: Store) -> None:
        self.store = store
        self._buses: dict[str, RunBus] = {}

    def create(self, run_id: str) -> RunBus:
        bus = RunBus(run_id, self.store)
        self._buses[run_id] = bus
        return bus

    def discard(self, run_id: str) -> None:
        self._buses.pop(run_id, None)

    def active_count(self) -> int:
        return sum(1 for b in self._buses.values() if not b.closed)

    async def subscribe(self, run_id: str, after: int = 0, heartbeat_s: float = 15.0) -> AsyncIterator[dict]:
        """Yield stored events after `after`, then live ones. Yields {} as a keep-alive."""
        last = after
        while True:
            # Read closed before the events, so a close racing this read cannot drop the tail.
            bus = self._buses.get(run_id)
            closed = bus is None or bus.closed
            events = await asyncio.to_thread(self.store.events, run_id, last)
            for event in events:
                last = event["seq"]
                yield event
            if closed:
                return
            if not events:
                await bus.wait_for_change(heartbeat_s)
                yield {}

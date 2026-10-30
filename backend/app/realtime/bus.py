"""Event bus for realtime clients.

`publish` is safe to call from the engine's loop task (it only enqueues on
per-client queues owned by that same loop; each writer uses put_nowait, slow
clients drop rather than backpressure the engine).
"""
from __future__ import annotations

import asyncio
import contextlib
from collections import deque

import orjson


class EventBus:
    def __init__(self, retention: int = 300) -> None:
        self._subs: list[asyncio.Queue[bytes]] = []
        self._recent: deque[tuple[str, dict]] = deque(maxlen=retention)

    def subscribe(self) -> asyncio.Queue[bytes]:
        q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=400)
        self._subs.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[bytes]) -> None:
        with contextlib.suppress(ValueError):
            self._subs.remove(q)

    def n_clients(self) -> int:
        return len(self._subs)

    def recent(self, limit: int = 50) -> list[tuple[str, dict]]:
        return list(self._recent)[-limit:]

    def publish(self, topic: str, data: dict) -> None:
        event = (topic, data)
        self._recent.append(event)
        payload = orjson.dumps({"topic": topic, "data": data})
        for q in tuple(self._subs):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                continue

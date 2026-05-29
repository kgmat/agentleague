"""Async event bus powering live monitoring.

Every meaningful runtime occurrence — a node starting, an inter-agent message,
a token-usage update, an error — is published here as a JSON-serialisable
``Event``. The monitoring WebSocket subscribes and streams these to the UI.

Two backends are provided behind one interface:

* ``RedisEventBus``    — pub/sub, works across processes (used in Docker).
* ``InMemoryEventBus`` — asyncio fan-out, zero-dependency local fallback.

The right backend is chosen automatically based on ``settings.REDIS_URL``.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Topic every event is also broadcast to, so a global monitor sees everything.
GLOBAL_TOPIC = "events:global"


def run_topic(run_id: str) -> str:
    return f"events:run:{run_id}"


@dataclass
class Event:
    """A single monitoring event."""

    type: str  # e.g. "node_start", "agent_message", "token_usage", "error", "run_status"
    run_id: str | None = None
    workflow_id: str | None = None
    agent_id: str | None = None
    agent_name: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)

    @staticmethod
    def from_json(raw: str) -> "Event":
        return Event(**json.loads(raw))


class EventBus:
    async def publish(self, event: Event) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def subscribe(self, topic: str) -> AsyncIterator[Event]:  # pragma: no cover
        raise NotImplementedError

    async def close(self) -> None:  # pragma: no cover - interface
        pass


class InMemoryEventBus(EventBus):
    """Single-process fan-out using per-subscriber asyncio queues."""

    def __init__(self) -> None:
        # topic -> set of subscriber queues
        self._subscribers: dict[str, set[asyncio.Queue[Event]]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, event: Event) -> None:
        topics = [GLOBAL_TOPIC]
        if event.run_id:
            topics.append(run_topic(event.run_id))
        async with self._lock:
            for topic in topics:
                for q in self._subscribers.get(topic, set()):
                    # Never block the publisher; drop on overflow.
                    if not q.full():
                        q.put_nowait(event)

    async def subscribe(self, topic: str) -> AsyncIterator[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=1000)
        async with self._lock:
            self._subscribers.setdefault(topic, set()).add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                self._subscribers.get(topic, set()).discard(queue)


class RedisEventBus(EventBus):
    """Cross-process fan-out using Redis pub/sub."""

    def __init__(self, url: str) -> None:
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(url, decode_responses=True)

    async def publish(self, event: Event) -> None:
        payload = event.to_json()
        await self._redis.publish(GLOBAL_TOPIC, payload)
        if event.run_id:
            await self._redis.publish(run_topic(event.run_id), payload)

    async def subscribe(self, topic: str) -> AsyncIterator[Event]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(topic)
        try:
            async for message in pubsub.listen():
                if message.get("type") == "message":
                    yield Event.from_json(message["data"])
        finally:
            await pubsub.unsubscribe(topic)
            await pubsub.close()

    async def close(self) -> None:
        await self._redis.aclose()


_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Return the process-wide singleton event bus."""
    global _bus
    if _bus is None:
        if settings.REDIS_URL:
            logger.info("Using Redis event bus at %s", settings.REDIS_URL)
            _bus = RedisEventBus(settings.REDIS_URL)
        else:
            logger.info("Using in-memory event bus (no REDIS_URL configured)")
            _bus = InMemoryEventBus()
    return _bus

"""
Lightweight in-process pub/sub used to push newly-ingested items to any
connected SSE clients in real time.

This in-process implementation is fine for a single backend instance.
The moment you run more than one backend process/replica, swap this for
Redis pub/sub (same publish/subscribe interface) so events reach clients
connected to a different instance than the one that handled the webhook.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from app.core.logging import get_logger

logger = get_logger(__name__)


class EventBus:
    def __init__(self) -> None:
        # user_id -> set of subscriber queues
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, user_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers[user_id].add(queue)
        logger.debug("New timeline subscriber for user=%s", user_id)
        return queue

    async def unsubscribe(self, user_id: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers[user_id].discard(queue)
            if not self._subscribers[user_id]:
                del self._subscribers[user_id]

    async def publish(self, user_id: str, event: dict) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(user_id, ()))
        for queue in queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Dropping timeline event for user=%s: subscriber queue full", user_id)


event_bus = EventBus()

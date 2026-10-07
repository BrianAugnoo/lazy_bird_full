"""Fan-out of scheduler events to asyncio subscribers (WebSocket connections).

The scheduler runs in threads; WebSockets live in the event loop. ``publish`` can
be called from any thread and delivers the event to every subscriber queue.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

QUEUE_SIZE = 1000


class EventHub:
    def __init__(self) -> None:
        self._subscribers: dict[asyncio.Queue, asyncio.AbstractEventLoop] = {}
        self._lock = threading.Lock()

    def subscribe(self) -> asyncio.Queue:
        """Return a queue receiving every future event; call from the event loop."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        with self._lock:
            self._subscribers[queue] = asyncio.get_running_loop()
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        with self._lock:
            self._subscribers.pop(queue, None)

    def publish(self, event: dict[str, Any]) -> None:
        with self._lock:
            subscribers = list(self._subscribers.items())
        for queue, loop in subscribers:
            try:
                loop.call_soon_threadsafe(_deliver, queue, event)
            except RuntimeError:
                self.unsubscribe(queue)


def _deliver(queue: asyncio.Queue, event: dict[str, Any]) -> None:
    if queue.full():
        queue.get_nowait()  # A slow client loses the oldest event rather than blocking everyone.
    queue.put_nowait(event)

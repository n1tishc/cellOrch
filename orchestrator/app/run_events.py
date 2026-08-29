"""In-process fan-out queues for dashboard run-state events."""
import asyncio

_subscribers: set[asyncio.Queue[dict]] = set()


def publish(event: dict) -> None:
    for queue in tuple(_subscribers):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass


def subscribe() -> asyncio.Queue[dict]:
    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=100)
    _subscribers.add(queue)
    return queue


def unsubscribe(queue: asyncio.Queue[dict]) -> None:
    _subscribers.discard(queue)

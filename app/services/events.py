import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


Event = tuple[str, dict]


class EventHub:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()
        self._last_payloads: dict[str, str] = {}

    @property
    def has_subscribers(self) -> bool:
        return bool(self._subscribers)

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[Event]]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=32)
        self._subscribers.add(queue)

        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    async def publish(self, event_type: str, payload: dict) -> None:
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        if self._last_payloads.get(event_type) == serialized:
            return

        self._last_payloads[event_type] = serialized

        for queue in tuple(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

            queue.put_nowait((event_type, payload))


event_hub = EventHub()

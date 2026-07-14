"""In-process pub/sub bus. Swap for Kafka/NATS in prod; same interface."""
from collections import defaultdict, deque
from typing import Callable, Awaitable
from pydantic import BaseModel
import asyncio
import logging

log = logging.getLogger(__name__)

Handler = Callable[[BaseModel], Awaitable[None] | None]


class MurmurationBus:
    def __init__(self, max_log: int = 5000):
        self._subs: dict[type, list[Handler]] = defaultdict(list)
        self._log: deque[BaseModel] = deque(maxlen=max_log)
        self._all_subs: list[Handler] = []

    async def publish(self, msg: BaseModel) -> None:
        self._log.append(msg)
        handlers = list(self._subs[type(msg)]) + list(self._all_subs)
        for handler in handlers:
            try:
                result = handler(msg)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                log.exception("bus handler failed for %s", type(msg).__name__)

    def subscribe(self, msg_type: type, handler: Handler) -> None:
        self._subs[msg_type].append(handler)

    def subscribe_all(self, handler: Handler) -> None:
        self._all_subs.append(handler)

    def replay(self, msg_type: type | None = None, limit: int = 200) -> list[BaseModel]:
        items = list(self._log)
        if msg_type is not None:
            items = [m for m in items if isinstance(m, msg_type)]
        return items[-limit:]

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

import redis.exceptions
import structlog

from pii_guard.core.models import MappingRecord
from pii_guard.store.base import MappingStore

_T = TypeVar("_T")


class FailoverStore:
    """Routes calls to a primary store, falling back on Redis connection errors."""

    def __init__(
        self,
        primary: MappingStore,
        fallback: MappingStore,
        retry_after_seconds: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._retry_after = retry_after_seconds
        self._clock = clock
        self._degraded = False
        self._degraded_until = 0.0
        self._last_warned = 0.0
        self._logger = structlog.get_logger()

    @property
    def backend(self) -> str:
        if self._degraded:
            return "redis-degraded"
        return "redis"

    async def get(self, key: str) -> MappingRecord | None:
        return await self._run(lambda store: store.get(key))

    async def put_if_absent(
        self, key: str, record: MappingRecord, ttl_seconds: int
    ) -> MappingRecord:
        return await self._run(lambda store: store.put_if_absent(key, record, ttl_seconds))

    async def ping(self) -> bool:
        return await self._run(lambda store: store.ping())

    async def close(self) -> None:
        await self._primary.close()
        await self._fallback.close()

    async def _run(self, op: Callable[[MappingStore], Awaitable[_T]]) -> _T:
        if self._degraded:
            if self._clock() >= self._degraded_until:
                try:
                    result = await op(self._primary)
                except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, OSError):
                    self._degraded_until = self._clock() + self._retry_after
                    self._warn()
                    return await op(self._fallback)
                self._degraded = False
                return result
            return await op(self._fallback)
        try:
            return await op(self._primary)
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, OSError):
            self._degraded = True
            self._degraded_until = self._clock() + self._retry_after
            self._warn()
            return await op(self._fallback)

    def _warn(self) -> None:
        now = self._clock()
        if now - self._last_warned >= self._retry_after:
            self._last_warned = now
            self._logger.warning("redis unavailable, using in-memory fallback")

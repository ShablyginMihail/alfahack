from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable

from pii_guard.core.codec import decode_record, encode_record
from pii_guard.core.models import MappingRecord
from pii_guard.store.crypto import RecordCipher


class MemoryStore:
    """In-process store holding encrypted blobs with TTL and LRU-style eviction."""

    backend = "memory"

    def __init__(
        self,
        cipher: RecordCipher,
        max_items: int = 500_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._cipher = cipher
        self._max_items = max_items
        self._clock = clock
        self._items: OrderedDict[str, tuple[float, bytes]] = OrderedDict()

    async def get(self, key: str) -> MappingRecord | None:
        item = self._items.get(key)
        if item is None:
            return None
        expires_at, blob = item
        if expires_at <= self._clock():
            del self._items[key]
            return None
        return decode_record(self._cipher.decrypt(key, blob))

    async def put_if_absent(
        self, key: str, record: MappingRecord, ttl_seconds: int
    ) -> MappingRecord:
        existing = await self.get(key)
        if existing is not None:
            return existing
        expires_at = self._clock() + ttl_seconds
        blob = self._cipher.encrypt(key, encode_record(record))
        self._items[key] = (expires_at, blob)
        self._items.move_to_end(key)
        while len(self._items) > self._max_items:
            self._items.popitem(last=False)
        return record

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self._items.clear()

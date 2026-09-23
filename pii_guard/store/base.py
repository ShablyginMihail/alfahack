from __future__ import annotations

from typing import Protocol

from pii_guard.core.models import MappingRecord


class MappingStore(Protocol):
    """Storage for payload_id -> MappingRecord, holding only encrypted bytes."""

    @property
    def backend(self) -> str:
        """One of "memory", "redis" or "redis-degraded"."""
        ...

    async def get(self, key: str) -> MappingRecord | None: ...

    async def put_if_absent(
        self, key: str, record: MappingRecord, ttl_seconds: int
    ) -> MappingRecord:
        """Atomically store the record unless the key already exists.

        Returns the existing record if present, otherwise the stored one.
        """
        ...

    async def put(self, key: str, record: MappingRecord, ttl_seconds: int) -> None:
        """Unconditionally store the record with a TTL, overwriting any existing one."""
        ...

    async def ping(self) -> bool: ...

    async def close(self) -> None: ...

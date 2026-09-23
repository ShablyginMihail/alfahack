from __future__ import annotations

import redis.asyncio as aioredis

from pii_guard.core.codec import decode_record, encode_record
from pii_guard.core.models import MappingRecord
from pii_guard.store.crypto import RecordCipher


def create_redis_client(url: str) -> aioredis.Redis:
    return aioredis.from_url(
        url,
        socket_timeout=0.5,
        socket_connect_timeout=0.5,
        health_check_interval=30,
        max_connections=200,
    )


def _as_bytes(value: bytes | str) -> bytes:
    return value if isinstance(value, bytes) else value.encode()


class RedisStore:
    """Redis-backed store using SET NX EX for atomic put-if-absent."""

    backend = "redis"

    def __init__(
        self,
        client: aioredis.Redis,
        cipher: RecordCipher,
        prefix: str = "pii:map:",
    ) -> None:
        self._client = client
        self._cipher = cipher
        self._prefix = prefix

    def _key(self, key: str) -> str:
        return self._prefix + key

    async def get(self, key: str) -> MappingRecord | None:
        blob = await self._client.get(self._key(key))
        if blob is None:
            return None
        return decode_record(self._cipher.decrypt(key, _as_bytes(blob)))

    async def put_if_absent(
        self, key: str, record: MappingRecord, ttl_seconds: int
    ) -> MappingRecord:
        full_key = self._key(key)
        blob = self._cipher.encrypt(key, encode_record(record))
        for _ in range(2):
            if await self._client.set(full_key, blob, nx=True, ex=ttl_seconds):
                return record
            existing = await self._client.get(full_key)
            if existing is not None:
                return decode_record(self._cipher.decrypt(key, _as_bytes(existing)))
        return record

    async def put(self, key: str, record: MappingRecord, ttl_seconds: int) -> None:
        full_key = self._key(key)
        blob = self._cipher.encrypt(key, encode_record(record))
        await self._client.set(full_key, blob, ex=ttl_seconds)

    async def ping(self) -> bool:
        return bool(await self._client.ping())

    async def close(self) -> None:
        await self._client.aclose()

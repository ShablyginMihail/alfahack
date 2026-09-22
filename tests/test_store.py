from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import redis.exceptions
from fakeredis import aioredis as fakeredis

from pii_guard.core.models import MappingRecord, Replacement
from pii_guard.store.crypto import RecordCipher, decode_key
from pii_guard.store.failover import FailoverStore
from pii_guard.store.memory import MemoryStore
from pii_guard.store.redis_store import RedisStore


@pytest.fixture
def cipher() -> RecordCipher:
    return RecordCipher(
        encryption_key=bytes(range(32)),
        hmac_key=bytes(range(32, 64)),
    )


@pytest.fixture
def record() -> MappingRecord:
    return MappingRecord(
        original_fp="a1b2c3",
        masked_text="Имя И. И., тел. 45** ****56",
        replacements=(
            Replacement(0, 9, 0, "Иванов Иван", "И. И.", "PERSON"),
            Replacement(15, 25, 15, "4509 123456", "45** ****56", "PHONE"),
        ),
    )


@pytest.fixture
def memory_store(cipher: RecordCipher) -> MemoryStore:
    return MemoryStore(cipher)


@pytest.fixture
async def redis_store(cipher: RecordCipher) -> AsyncIterator[RedisStore]:
    client = fakeredis.FakeRedis()
    store = RedisStore(client, cipher)
    yield store
    await store.close()


class TestCrypto:
    def test_encrypt_decrypt_roundtrip(self, cipher: RecordCipher) -> None:
        data = b"secret payload"
        blob = cipher.encrypt("key-1", data)
        assert blob != data
        assert cipher.decrypt("key-1", blob) == data

    def test_decrypt_wrong_record_key_raises(self, cipher: RecordCipher) -> None:
        blob = cipher.encrypt("key-1", b"data")
        with pytest.raises(ValueError):
            cipher.decrypt("key-2", blob)

    def test_decrypt_corrupted_blob_raises(self, cipher: RecordCipher) -> None:
        blob = cipher.encrypt("key-1", b"data")
        corrupted = blob[:-1] + bytes([blob[-1] ^ 0xFF])
        with pytest.raises(ValueError):
            cipher.decrypt("key-1", corrupted)

    def test_decode_key_wrong_length_raises(self) -> None:
        import base64

        encoded = base64.b64encode(b"short").decode()
        with pytest.raises(ValueError):
            decode_key(encoded)

    def test_decode_key_none_generates_32_bytes(self) -> None:
        key = decode_key(None)
        assert len(key) == 32

    def test_fingerprint_is_hex(self, cipher: RecordCipher) -> None:
        fp = cipher.fingerprint("текст")
        assert len(fp) == 64
        int(fp, 16)


class TestMemoryStore:
    async def test_get_missing_returns_none(self, memory_store: MemoryStore) -> None:
        assert await memory_store.get("nope") is None

    async def test_put_and_get(self, memory_store: MemoryStore, record: MappingRecord) -> None:
        stored = await memory_store.put_if_absent("k", record, ttl_seconds=60)
        assert stored == record
        assert await memory_store.get("k") == record

    async def test_put_if_absent_keeps_first(
        self, memory_store: MemoryStore, record: MappingRecord
    ) -> None:
        other = MappingRecord(original_fp="zzz", masked_text="другое", replacements=())
        await memory_store.put_if_absent("k", record, ttl_seconds=60)
        assert await memory_store.put_if_absent("k", other, ttl_seconds=60) == record
        assert await memory_store.get("k") == record

    async def test_expiry(self, cipher: RecordCipher, record: MappingRecord) -> None:
        now = 1000.0
        store = MemoryStore(cipher, clock=lambda: now)
        await store.put_if_absent("k", record, ttl_seconds=10)
        now += 11
        assert await store.get("k") is None

    async def test_eviction(self, cipher: RecordCipher, record: MappingRecord) -> None:
        store = MemoryStore(cipher, max_items=2)
        await store.put_if_absent("a", record, ttl_seconds=60)
        await store.put_if_absent("b", record, ttl_seconds=60)
        await store.put_if_absent("c", record, ttl_seconds=60)
        assert await store.get("a") is None
        assert await store.get("b") == record
        assert await store.get("c") == record


class TestRedisStore:
    async def test_get_missing_returns_none(self, redis_store: RedisStore) -> None:
        assert await redis_store.get("nope") is None

    async def test_put_and_get(self, redis_store: RedisStore, record: MappingRecord) -> None:
        stored = await redis_store.put_if_absent("k", record, ttl_seconds=60)
        assert stored == record
        assert await redis_store.get("k") == record

    async def test_put_if_absent_keeps_first(
        self, redis_store: RedisStore, record: MappingRecord
    ) -> None:
        other = MappingRecord(original_fp="zzz", masked_text="другое", replacements=())
        await redis_store.put_if_absent("k", record, ttl_seconds=60)
        assert await redis_store.put_if_absent("k", other, ttl_seconds=60) == record
        assert await redis_store.get("k") == record

    async def test_ttl_set(self, redis_store: RedisStore, record: MappingRecord) -> None:
        await redis_store.put_if_absent("k", record, ttl_seconds=60)
        ttl = await redis_store._client.ttl("pii:map:k")
        assert ttl > 0

    async def test_raw_bytes_do_not_leak_original(
        self, redis_store: RedisStore, record: MappingRecord
    ) -> None:
        await redis_store.put_if_absent("k", record, ttl_seconds=60)
        raw = await redis_store._client.get("pii:map:k")
        assert raw is not None
        raw_bytes = bytes(raw)
        assert b"4509 123456" not in raw_bytes
        assert b"45** ****56" not in raw_bytes


class _FakeStore:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self._data: dict[str, MappingRecord] = {}
        self.calls = 0

    @property
    def backend(self) -> str:
        return "fake"

    async def get(self, key: str) -> MappingRecord | None:
        self.calls += 1
        if self._fail:
            raise redis.exceptions.ConnectionError("down")
        return self._data.get(key)

    async def put_if_absent(
        self, key: str, record: MappingRecord, ttl_seconds: int
    ) -> MappingRecord:
        self.calls += 1
        if self._fail:
            raise redis.exceptions.ConnectionError("down")
        return self._data.setdefault(key, record)

    async def ping(self) -> bool:
        self.calls += 1
        if self._fail:
            raise redis.exceptions.ConnectionError("down")
        return True

    async def close(self) -> None:
        # Фейковому клиенту нечего освобождать.
        pass


class TestFailoverStore:
    async def test_fallback_on_connection_error(self, record: MappingRecord) -> None:
        now = 0.0
        primary = _FakeStore(fail=True)
        fallback = _FakeStore()
        store = FailoverStore(primary, fallback, retry_after_seconds=5.0, clock=lambda: now)

        assert store.backend == "redis"
        await store.put_if_absent("k", record, ttl_seconds=60)
        assert store.backend == "redis-degraded"
        assert fallback.calls == 1
        assert await store.get("k") == record
        assert fallback.calls == 2

    async def test_recovers_to_primary(self, record: MappingRecord) -> None:
        now = 0.0
        primary = _FakeStore(fail=True)
        fallback = _FakeStore()
        store = FailoverStore(primary, fallback, retry_after_seconds=5.0, clock=lambda: now)

        await store.put_if_absent("k", record, ttl_seconds=60)
        assert store.backend == "redis-degraded"

        primary._fail = False
        now += 6
        await store.get("k")
        assert store.backend == "redis"
        assert primary.calls == 2

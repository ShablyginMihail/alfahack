from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager

import pytest
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient

from pii_guard.core.engine import Engine
from pii_guard.core.masking import DefaultMasker
from pii_guard.core.models import Span
from pii_guard.core.normalize import Document
from pii_guard.core.policy import CHECKER_PROFILE
from pii_guard.core.registry import RecognizerRegistry
from pii_guard.core.types import default_type_registry
from pii_guard.main import create_app
from pii_guard.services.process import ProcessService
from pii_guard.settings import Settings
from pii_guard.store.crypto import RecordCipher, decode_key
from pii_guard.store.redis_store import RedisStore

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PASSPORT_RE = re.compile(r"\b4509 123456\b")


class FakeRecognizer:
    name = "fake"
    pii_types = frozenset({"EMAIL", "PASSPORT"})

    def find(self, doc: Document) -> list[Span]:
        spans: list[Span] = []
        for match in EMAIL_RE.finditer(doc.text):
            spans.append(
                Span(
                    start=match.start(),
                    end=match.end(),
                    pii_type="EMAIL",
                    score=1.0,
                    recognizer=self.name,
                )
            )
        for match in PASSPORT_RE.finditer(doc.text):
            spans.append(
                Span(
                    start=match.start(),
                    end=match.end(),
                    pii_type="PASSPORT",
                    score=1.0,
                    recognizer=self.name,
                )
            )
        return spans


def _registry() -> RecognizerRegistry:
    registry = RecognizerRegistry()
    registry.register(FakeRecognizer())
    return registry


def _settings() -> Settings:
    return Settings(
        redis_url=None,
        max_body_bytes=1000,
        log_level="WARNING",
        encryption_key=None,
        hmac_key=None,
    )


async def _client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@asynccontextmanager
async def _start_lifespan(app):
    async with app.router.lifespan_context(app):
        yield


@pytest.mark.asyncio
async def test_mask_then_unmask_roundtrip() -> None:
    app = create_app(_settings(), registry=_registry())
    async with _start_lifespan(app), await _client(app) as client:
        text = "Клиент Иванов Иван, email ivanov@mail.ru, паспорт 4509 123456"
        resp = await client.post("/process", json={"payload": text, "payload_id": "id-1"})
        assert resp.status_code == 200
        masked = resp.json()["result"]
        assert "ivanov@mail.ru" not in masked
        assert "4509 123456" not in masked

        resp2 = await client.post("/process", json={"payload": masked, "payload_id": "id-1"})
        assert resp2.status_code == 200
        assert resp2.json()["result"] == text


@pytest.mark.asyncio
async def test_mask_retry_same_mask() -> None:
    app = create_app(_settings(), registry=_registry())
    async with _start_lifespan(app), await _client(app) as client:
        text = "email ivanov@mail.ru"
        r1 = await client.post("/process", json={"payload": text, "payload_id": "id-2"})
        r2 = await client.post("/process", json={"payload": text, "payload_id": "id-2"})
        assert r1.json()["result"] == r2.json()["result"]


@pytest.mark.asyncio
async def test_unmask_retry_returns_original() -> None:
    app = create_app(_settings(), registry=_registry())
    async with _start_lifespan(app), await _client(app) as client:
        text = "email ivanov@mail.ru"
        r1 = await client.post("/process", json={"payload": text, "payload_id": "id-3"})
        masked = r1.json()["result"]
        r2 = await client.post("/process", json={"payload": masked, "payload_id": "id-3"})
        r3 = await client.post("/process", json={"payload": masked, "payload_id": "id-3"})
        assert r2.json()["result"] == text
        assert r3.json()["result"] == text


@pytest.mark.asyncio
async def test_no_pii_unchanged_both_steps() -> None:
    app = create_app(_settings(), registry=_registry())
    async with _start_lifespan(app), await _client(app) as client:
        text = "просто текст без персональных данных"
        r1 = await client.post("/process", json={"payload": text, "payload_id": "id-4"})
        assert r1.json()["result"] == text
        r2 = await client.post("/process", json={"payload": text, "payload_id": "id-4"})
        assert r2.json()["result"] == text


@pytest.mark.asyncio
async def test_concurrent_mask_same_id() -> None:
    app = create_app(_settings(), registry=_registry())
    async with _start_lifespan(app), await _client(app) as client:
        text = "email ivanov@mail.ru"

        async def post():
            return await client.post("/process", json={"payload": text, "payload_id": "id-5"})

        r1, r2 = await asyncio.gather(post(), post())
        assert r1.json()["result"] == r2.json()["result"]
        masked = r1.json()["result"]
        r3 = await client.post("/process", json={"payload": masked, "payload_id": "id-5"})
        assert r3.json()["result"] == text


@pytest.mark.asyncio
async def test_changed_text_fragment_replaced() -> None:
    app = create_app(_settings(), registry=_registry())
    async with _start_lifespan(app), await _client(app) as client:
        text = "email ivanov@mail.ru"
        r1 = await client.post("/process", json={"payload": text, "payload_id": "id-6"})
        masked = r1.json()["result"]
        changed = f"перезвоните на {masked} пожалуйста"
        r2 = await client.post("/process", json={"payload": changed, "payload_id": "id-6"})
        assert "ivanov@mail.ru" in r2.json()["result"]


@pytest.mark.asyncio
async def test_ready_memory_store() -> None:
    app = create_app(_settings(), registry=_registry())
    async with _start_lifespan(app), await _client(app) as client:
        resp = await client.get("/ready")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ready", "store": "memory", "degraded": False}


@pytest.mark.asyncio
async def test_process_service_two_workers_shared_redis() -> None:
    cipher = RecordCipher(decode_key(None), decode_key(None))
    redis = FakeRedis()
    store = RedisStore(redis, cipher)
    engine = Engine(_registry(), DefaultMasker(default_type_registry()))

    worker1 = ProcessService(engine, store, cipher, CHECKER_PROFILE, ttl_seconds=60)
    worker2 = ProcessService(engine, store, cipher, CHECKER_PROFILE, ttl_seconds=60)

    text = "email ivanov@mail.ru"
    out1 = await worker1.handle("shared-id", text)
    assert out1.direction == "mask"
    assert "ivanov@mail.ru" not in out1.result

    out2 = await worker2.handle("shared-id", out1.result)
    assert out2.direction == "unmask"
    assert out2.result == text

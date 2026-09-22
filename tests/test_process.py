from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient

from pii_guard.config.loader import ConfigStore
from pii_guard.main import create_app
from pii_guard.services.process import ProcessService
from pii_guard.settings import Settings
from pii_guard.store.crypto import RecordCipher, decode_key
from pii_guard.store.redis_store import RedisStore
from tests.helpers import make_settings, write_config


def _settings(tmp_path) -> Settings:
    return make_settings(tmp_path)


def _full_settings(tmp_path) -> Settings:
    settings = make_settings(tmp_path, recognizer_modules=Settings().recognizer_modules)
    write_config(
        settings.config_dir,
        systems={
            "defaults": {"mask_style": "partial", "unmask": True, "strict": False},
            "systems": {
                "checker": {
                    "enabled": True,
                    "pii_types": "all",
                    "mask_style": "full",
                }
            },
        },
    )
    return settings


async def _client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@asynccontextmanager
async def _start_lifespan(app):
    async with app.router.lifespan_context(app):
        yield


@pytest.mark.asyncio
async def test_mask_then_unmask_roundtrip(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
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
async def test_mask_retry_same_mask(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
    async with _start_lifespan(app), await _client(app) as client:
        text = "email ivanov@mail.ru"
        r1 = await client.post("/process", json={"payload": text, "payload_id": "id-2"})
        r2 = await client.post("/process", json={"payload": text, "payload_id": "id-2"})
        assert r1.json()["result"] == r2.json()["result"]


@pytest.mark.asyncio
async def test_unmask_retry_returns_original(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
    async with _start_lifespan(app), await _client(app) as client:
        text = "email ivanov@mail.ru"
        r1 = await client.post("/process", json={"payload": text, "payload_id": "id-3"})
        masked = r1.json()["result"]
        r2 = await client.post("/process", json={"payload": masked, "payload_id": "id-3"})
        r3 = await client.post("/process", json={"payload": masked, "payload_id": "id-3"})
        assert r2.json()["result"] == text
        assert r3.json()["result"] == text


@pytest.mark.asyncio
async def test_no_pii_unchanged_both_steps(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
    async with _start_lifespan(app), await _client(app) as client:
        text = "просто текст без персональных данных"
        r1 = await client.post("/process", json={"payload": text, "payload_id": "id-4"})
        assert r1.json()["result"] == text
        r2 = await client.post("/process", json={"payload": text, "payload_id": "id-4"})
        assert r2.json()["result"] == text


@pytest.mark.asyncio
async def test_concurrent_mask_same_id(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
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
async def test_changed_text_fragment_replaced(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
    async with _start_lifespan(app), await _client(app) as client:
        text = "email ivanov@mail.ru"
        r1 = await client.post("/process", json={"payload": text, "payload_id": "id-6"})
        masked = r1.json()["result"]
        changed = f"перезвоните на {masked} пожалуйста"
        r2 = await client.post("/process", json={"payload": changed, "payload_id": "id-6"})
        assert "ivanov@mail.ru" in r2.json()["result"]


@pytest.mark.asyncio
async def test_ready_memory_store(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
    async with _start_lifespan(app), await _client(app) as client:
        resp = await client.get("/ready")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ready", "store": "memory", "degraded": False}


@pytest.mark.asyncio
async def test_process_service_two_workers_shared_redis(tmp_path) -> None:
    cipher = RecordCipher(decode_key(None), decode_key(None))
    redis = FakeRedis()
    store = RedisStore(redis, cipher)
    settings = _settings(tmp_path)
    config_store = ConfigStore(settings.config_dir, settings.recognizer_modules)

    worker1 = ProcessService(config_store, store, cipher, ttl_seconds=60)
    worker2 = ProcessService(config_store, store, cipher, ttl_seconds=60)

    text = "email ivanov@mail.ru"
    out1 = await worker1.handle("shared-id", text)
    assert out1.direction == "mask"
    assert "ivanov@mail.ru" not in out1.result

    out2 = await worker2.handle("shared-id", out1.result)
    assert out2.direction == "unmask"
    assert out2.result == text


@pytest.mark.asyncio
async def test_full_mask_roundtrip(tmp_path) -> None:
    app = create_app(_full_settings(tmp_path))
    async with _start_lifespan(app), await _client(app) as client:
        text = "Клиент Иванов Иван Иванович, паспорт 4509 123456"
        resp = await client.post("/process", json={"payload": text, "payload_id": "full-1"})
        assert resp.status_code == 200
        masked = resp.json()["result"]
        assert not any(ch.isdigit() for ch in masked)
        assert "Иванов Иван Иванович" not in masked
        assert "4509 123456" not in masked

        resp2 = await client.post("/process", json={"payload": masked, "payload_id": "full-1"})
        assert resp2.status_code == 200
        assert resp2.json()["result"] == text

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient

from pii_guard.config.loader import ConfigStore
from pii_guard.core.concurrency import ConcurrencyGate
from pii_guard.main import create_app
from pii_guard.services.process import ProcessService
from pii_guard.settings import Settings
from pii_guard.store.crypto import RecordCipher, decode_key
from pii_guard.store.redis_store import RedisStore
from tests.helpers import make_settings, write_config

PROCESS_PATH = "/process"
EMAIL = "ivanov@mail.ru"
EMAIL_TEXT = "email ivanov@mail.ru"
TEXT1 = "Клиент Иванов Иван Иванович, паспорт 4509 123456"
TEXT2 = "Клиент Петрова Мария Сергеевна, телефон +7 916 123-45-67"
NEW_ID = "id-new"


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
        resp = await client.post(PROCESS_PATH, json={"payload": text, "payload_id": "id-1"})
        assert resp.status_code == 200
        masked = resp.json()["result"]
        assert EMAIL not in masked
        assert "4509 123456" not in masked

        resp2 = await client.post(PROCESS_PATH, json={"payload": masked, "payload_id": "id-1"})
        assert resp2.status_code == 200
        assert resp2.json()["result"] == text


@pytest.mark.asyncio
async def test_mask_retry_same_mask(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
    async with _start_lifespan(app), await _client(app) as client:
        text = EMAIL_TEXT
        r1 = await client.post(PROCESS_PATH, json={"payload": text, "payload_id": "id-2"})
        r2 = await client.post(PROCESS_PATH, json={"payload": text, "payload_id": "id-2"})
        assert r1.json()["result"] == r2.json()["result"]


@pytest.mark.asyncio
async def test_unmask_retry_returns_original(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
    async with _start_lifespan(app), await _client(app) as client:
        text = EMAIL_TEXT
        r1 = await client.post(PROCESS_PATH, json={"payload": text, "payload_id": "id-3"})
        masked = r1.json()["result"]
        r2 = await client.post(PROCESS_PATH, json={"payload": masked, "payload_id": "id-3"})
        r3 = await client.post(PROCESS_PATH, json={"payload": masked, "payload_id": "id-3"})
        assert r2.json()["result"] == text
        assert r3.json()["result"] == text


@pytest.mark.asyncio
async def test_no_pii_unchanged_both_steps(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
    async with _start_lifespan(app), await _client(app) as client:
        text = "просто текст без персональных данных"
        r1 = await client.post(PROCESS_PATH, json={"payload": text, "payload_id": "id-4"})
        assert r1.json()["result"] == text
        r2 = await client.post(PROCESS_PATH, json={"payload": text, "payload_id": "id-4"})
        assert r2.json()["result"] == text


@pytest.mark.asyncio
async def test_concurrent_mask_same_id(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
    async with _start_lifespan(app), await _client(app) as client:
        text = EMAIL_TEXT

        async def post():
            return await client.post(PROCESS_PATH, json={"payload": text, "payload_id": "id-5"})

        r1, r2 = await asyncio.gather(post(), post())
        assert r1.json()["result"] == r2.json()["result"]
        masked = r1.json()["result"]
        r3 = await client.post(PROCESS_PATH, json={"payload": masked, "payload_id": "id-5"})
        assert r3.json()["result"] == text


@pytest.mark.asyncio
async def test_changed_text_fragment_replaced(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
    async with _start_lifespan(app), await _client(app) as client:
        text = EMAIL_TEXT
        r1 = await client.post(PROCESS_PATH, json={"payload": text, "payload_id": "id-6"})
        masked = r1.json()["result"]
        changed = f"перезвоните на {masked} пожалуйста"
        r2 = await client.post(PROCESS_PATH, json={"payload": changed, "payload_id": "id-6"})
        assert EMAIL in r2.json()["result"]


@pytest.mark.asyncio
async def test_same_id_new_text_replaces_mask(tmp_path) -> None:
    app = create_app(_full_settings(tmp_path))
    async with _start_lifespan(app), await _client(app) as client:
        text1 = TEXT1
        text2 = TEXT2
        r1 = await client.post(PROCESS_PATH, json={"payload": text1, "payload_id": NEW_ID})
        masked1 = r1.json()["result"]
        r2 = await client.post(PROCESS_PATH, json={"payload": text2, "payload_id": NEW_ID})
        assert r2.status_code == 200
        masked2 = r2.json()["result"]
        assert masked2 != masked1
        assert "Петрова Мария Сергеевна" not in masked2
        assert "+7 916 123-45-67" not in masked2


@pytest.mark.asyncio
async def test_same_id_new_mask_unmask_roundtrip(tmp_path) -> None:
    app = create_app(_full_settings(tmp_path))
    async with _start_lifespan(app), await _client(app) as client:
        text1 = TEXT1
        text2 = TEXT2
        await client.post(PROCESS_PATH, json={"payload": text1, "payload_id": NEW_ID})
        r2 = await client.post(PROCESS_PATH, json={"payload": text2, "payload_id": NEW_ID})
        masked2 = r2.json()["result"]
        r3 = await client.post(PROCESS_PATH, json={"payload": masked2, "payload_id": NEW_ID})
        assert r3.json()["result"] == text2


@pytest.mark.asyncio
async def test_same_id_repeat_original_same_mask(tmp_path) -> None:
    app = create_app(_full_settings(tmp_path))
    async with _start_lifespan(app), await _client(app) as client:
        text1 = TEXT1
        text2 = TEXT2
        r1 = await client.post(PROCESS_PATH, json={"payload": text1, "payload_id": NEW_ID})
        masked1 = r1.json()["result"]
        await client.post(PROCESS_PATH, json={"payload": text2, "payload_id": NEW_ID})
        r4 = await client.post(PROCESS_PATH, json={"payload": text1, "payload_id": NEW_ID})
        assert r4.json()["result"] == masked1


@pytest.mark.asyncio
async def test_long_payload_id_accepted(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
    async with _start_lifespan(app), await _client(app) as client:
        long_id = "x" * 300
        resp = await client.post(PROCESS_PATH, json={"payload": EMAIL_TEXT, "payload_id": long_id})
        assert resp.status_code == 200


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

    text = EMAIL_TEXT
    out1 = await worker1.handle("shared-id", text)
    assert out1.direction == "mask"
    assert EMAIL not in out1.result

    out2 = await worker2.handle("shared-id", out1.result)
    assert out2.direction == "unmask"
    assert out2.result == text


@pytest.mark.asyncio
async def test_full_mask_roundtrip(tmp_path) -> None:
    app = create_app(_full_settings(tmp_path))
    async with _start_lifespan(app), await _client(app) as client:
        text = TEXT1
        resp = await client.post(PROCESS_PATH, json={"payload": text, "payload_id": "full-1"})
        assert resp.status_code == 200
        masked = resp.json()["result"]
        assert not any(ch.isdigit() for ch in masked)
        assert "Иванов Иван Иванович" not in masked
        assert "4509 123456" not in masked

        resp2 = await client.post(PROCESS_PATH, json={"payload": masked, "payload_id": "full-1"})
        assert resp2.status_code == 200
        assert resp2.json()["result"] == text


def test_concurrency_gate_limits_and_releases() -> None:
    gate = ConcurrencyGate(limit=2)
    assert gate.try_enter() is True
    assert gate.try_enter() is True
    assert gate.try_enter() is False
    gate.exit()
    assert gate.try_enter() is True
    assert gate.try_enter() is False


@pytest.mark.asyncio
async def test_process_overloaded_returns_429(tmp_path) -> None:
    settings = make_settings(tmp_path, max_concurrent_process=1)
    app = create_app(settings)
    async with _start_lifespan(app), await _client(app) as client:
        gate = app.state.concurrency_gate
        assert gate.try_enter() is True
        resp = await client.post(PROCESS_PATH, json={"payload": EMAIL_TEXT, "payload_id": "id-7"})
        assert resp.status_code == 429
        assert resp.json() == {"error": "overloaded"}
        assert resp.headers["retry-after"] == "1"
        gate.exit()
        resp2 = await client.post(PROCESS_PATH, json={"payload": EMAIL_TEXT, "payload_id": "id-7"})
        assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_process_overloaded_by_weight_returns_429(tmp_path) -> None:
    settings = make_settings(tmp_path, max_inflight_chars=10)
    app = create_app(settings)
    async with _start_lifespan(app), await _client(app) as client:
        gate = app.state.concurrency_gate
        assert gate.try_enter(weight=10) is True
        resp = await client.post(PROCESS_PATH, json={"payload": EMAIL_TEXT, "payload_id": "id-8"})
        assert resp.status_code == 429
        assert resp.json() == {"error": "overloaded"}
        assert resp.headers["retry-after"] == "1"
        gate.exit(weight=10)
        resp2 = await client.post(PROCESS_PATH, json={"payload": EMAIL_TEXT, "payload_id": "id-8"})
        assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_process_fail_open_with_failing_recognizer(tmp_path) -> None:
    settings = make_settings(tmp_path, recognizer_modules=["tests.fake_failing_recognizers"])
    app = create_app(settings)
    async with _start_lifespan(app), await _client(app) as client:
        resp = await client.post(PROCESS_PATH, json={"payload": EMAIL_TEXT, "payload_id": "id-9"})
        assert resp.status_code == 200

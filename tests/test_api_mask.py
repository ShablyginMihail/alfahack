from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from pii_guard.main import create_app
from pii_guard.settings import Settings
from tests.helpers import make_settings, write_config

TOKEN_KEY = "token-key"
LABEL_KEY = "label-key"
OTHER_TOKEN_KEY = "other-token-key"
DISABLED_KEY = "disabled-key"
ADMIN_TOKEN = "admin-secret"


def _sha(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _systems_config() -> dict:
    return {
        "defaults": {"mask_style": "partial", "unmask": True, "strict": False},
        "systems": {
            "checker": {
                "enabled": True,
                "pii_types": "all",
                "mask_style": "partial",
            },
            "token-sys": {
                "enabled": True,
                "pii_types": "all",
                "mask_style": "token",
                "unmask": True,
                "api_key_sha256": _sha(TOKEN_KEY),
            },
            "label-sys": {
                "enabled": True,
                "pii_types": ["EMAIL"],
                "mask_style": "label",
                "unmask": False,
                "api_key_sha256": _sha(LABEL_KEY),
            },
            "other-token-sys": {
                "enabled": True,
                "pii_types": "all",
                "mask_style": "token",
                "unmask": True,
                "api_key_sha256": _sha(OTHER_TOKEN_KEY),
            },
            "disabled-sys": {
                "enabled": False,
                "pii_types": "all",
                "mask_style": "partial",
                "api_key_sha256": _sha(DISABLED_KEY),
            },
        },
    }


def _settings(tmp_path, **overrides) -> Settings:
    settings = make_settings(tmp_path, **overrides)
    write_config(settings.config_dir, systems=_systems_config())
    return settings


@asynccontextmanager
async def _client_for(settings: Settings):
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as c,
    ):
        yield c


@pytest.mark.asyncio
async def test_token_roundtrip(tmp_path) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as client:
        headers = {"X-API-Key": TOKEN_KEY}
        text = "email ivanov@mail.ru, паспорт 4509 123456"
        resp = await client.post("/api/v1/mask", json={"text": text}, headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        masked = body["masked_text"]
        assert "ivanov@mail.ru" not in masked
        assert "4509 123456" not in masked
        assert "[EMAIL_1]" in masked
        assert "[ПАСПОРТ_1]" in masked

        unmask = await client.post(
            "/api/v1/unmask",
            json={"session_id": body["session_id"], "text": masked},
            headers=headers,
        )
        assert unmask.status_code == 200
        assert unmask.json()["text"] == text


@pytest.mark.asyncio
async def test_label_style_unmask_disabled(tmp_path) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as client:
        headers = {"X-API-Key": LABEL_KEY}
        text = "email ivanov@mail.ru, паспорт 4509 123456"
        resp = await client.post("/api/v1/mask", json={"text": text}, headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        masked = body["masked_text"]
        assert "[EMAIL]" in masked
        assert "4509 123456" in masked

        unmask = await client.post(
            "/api/v1/unmask",
            json={"session_id": body["session_id"], "text": masked},
            headers=headers,
        )
        assert unmask.status_code == 403
        assert unmask.json() == {"error": "unmask_disabled"}


@pytest.mark.asyncio
async def test_missing_api_key(tmp_path) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as client:
        resp = await client.post("/api/v1/mask", json={"text": "email ivanov@mail.ru"})
        assert resp.status_code == 401
        assert resp.json() == {"error": "missing_api_key"}


@pytest.mark.asyncio
async def test_wrong_api_key(tmp_path) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as client:
        resp = await client.post(
            "/api/v1/mask",
            json={"text": "email ivanov@mail.ru"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 401
        assert resp.json() == {"error": "invalid_api_key"}


@pytest.mark.asyncio
async def test_disabled_system(tmp_path) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as client:
        resp = await client.post(
            "/api/v1/mask",
            json={"text": "email ivanov@mail.ru"},
            headers={"X-API-Key": DISABLED_KEY},
        )
        assert resp.status_code == 403
        assert resp.json() == {"error": "system_disabled"}


@pytest.mark.asyncio
async def test_session_id_not_shared_between_systems(tmp_path) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as client:
        token_headers = {"X-API-Key": TOKEN_KEY}
        other_headers = {"X-API-Key": OTHER_TOKEN_KEY}
        text = "email ivanov@mail.ru"
        resp = await client.post("/api/v1/mask", json={"text": text}, headers=token_headers)
        session_id = resp.json()["session_id"]
        masked = resp.json()["masked_text"]

        unmask = await client.post(
            "/api/v1/unmask",
            json={"session_id": session_id, "text": masked},
            headers=other_headers,
        )
        assert unmask.status_code == 404
        assert unmask.json() == {"error": "session_not_found"}


@pytest.mark.asyncio
async def test_admin_config_no_token_404(tmp_path) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as client:
        resp = await client.get("/admin/config")
        assert resp.status_code == 404
        assert resp.json() == {"error": "not_found"}


@pytest.mark.asyncio
async def test_admin_config_wrong_token_401(tmp_path) -> None:
    settings = _settings(tmp_path, admin_token=ADMIN_TOKEN)
    async with _client_for(settings) as client:
        resp = await client.get("/admin/config", headers={"X-Admin-Token": "wrong"})
        assert resp.status_code == 401
        assert resp.json() == {"error": "invalid_admin_token"}


@pytest.mark.asyncio
async def test_admin_config_ok_no_key_hashes(tmp_path) -> None:
    settings = _settings(tmp_path, admin_token=ADMIN_TOKEN)
    async with _client_for(settings) as client:
        resp = await client.get("/admin/config", headers={"X-Admin-Token": ADMIN_TOKEN})
        assert resp.status_code == 200
        body = resp.json()
        assert "token-sys" in body["systems"]
        assert "label-sys" in body["systems"]
        assert "disabled-sys" in body["systems"]
        assert body["systems"]["disabled-sys"]["enabled"] is False
        for system in body["systems"].values():
            assert "api_key_sha256" not in system


@pytest.mark.asyncio
async def test_admin_reload_picks_up_changes(tmp_path) -> None:
    settings = _settings(tmp_path, admin_token=ADMIN_TOKEN)
    async with _client_for(settings) as client:
        headers = {"X-Admin-Token": ADMIN_TOKEN}
        config_dir = settings.config_dir

        resp = await client.get("/admin/config", headers=headers)
        assert resp.json()["systems"]["token-sys"]["mask_style"] == "token"

        systems = _systems_config()
        systems["systems"]["token-sys"]["mask_style"] = "label"
        write_config(config_dir, systems=systems)

        reload = await client.post("/admin/reload", headers=headers)
        assert reload.status_code == 200
        assert reload.json() == {"status": "reloaded"}

        resp2 = await client.get("/admin/config", headers=headers)
        assert resp2.json()["systems"]["token-sys"]["mask_style"] == "label"


@pytest.mark.asyncio
async def test_process_with_checker_profile(tmp_path) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as client:
        text = "email ivanov@mail.ru, паспорт 4509 123456"
        resp = await client.post("/process", json={"payload": text, "payload_id": "p-1"})
        assert resp.status_code == 200
        masked = resp.json()["result"]
        assert "ivanov@mail.ru" not in masked
        assert "4509 123456" not in masked

        resp2 = await client.post("/process", json={"payload": masked, "payload_id": "p-1"})
        assert resp2.status_code == 200
        assert resp2.json()["result"] == text


@pytest.mark.asyncio
async def test_mask_overloaded_returns_429(tmp_path) -> None:
    settings = _settings(tmp_path, max_concurrent_process=1)
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        gate = app.state.concurrency_gate
        assert gate.try_enter() is True
        resp = await client.post(
            "/api/v1/mask",
            json={"text": "email ivanov@mail.ru"},
            headers={"X-API-Key": TOKEN_KEY},
        )
        assert resp.status_code == 429
        assert resp.json() == {"error": "overloaded"}
        assert resp.headers["retry-after"] == "1"
        gate.exit()
        resp2 = await client.post(
            "/api/v1/mask",
            json={"text": "email ivanov@mail.ru"},
            headers={"X-API-Key": TOKEN_KEY},
        )
        assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_unmask_overloaded_returns_429(tmp_path) -> None:
    settings = _settings(tmp_path, max_concurrent_process=1)
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        gate = app.state.concurrency_gate
        assert gate.try_enter() is True
        resp = await client.post(
            "/api/v1/unmask",
            json={"session_id": "sess", "text": "text"},
            headers={"X-API-Key": TOKEN_KEY},
        )
        assert resp.status_code == 429
        assert resp.json() == {"error": "overloaded"}
        assert resp.headers["retry-after"] == "1"
        gate.exit()
        resp2 = await client.post(
            "/api/v1/unmask",
            json={"session_id": "sess", "text": "text"},
            headers={"X-API-Key": TOKEN_KEY},
        )
        assert resp2.status_code == 404

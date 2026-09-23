from __future__ import annotations

import hashlib
import secrets
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from pii_guard.llm.client import LLMError
from pii_guard.main import create_app
from pii_guard.settings import Settings
from tests.helpers import make_settings, write_config

TOKEN_KEY = secrets.token_urlsafe(16)
NO_UNMASK_KEY = secrets.token_urlsafe(16)
SYNTHETIC_KEY = secrets.token_urlsafe(16)

CHAT_PATH = "/v1/chat/completions"
IVANOV = "Иванов"
IVANOV_FULL = "Иванов Иван Иванович"
PHONE_PLAIN = "+7 916 123-45-67"


def _sha(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _systems_config() -> dict:
    return {
        "defaults": {"mask_style": "partial", "unmask": True, "strict": False},
        "systems": {
            "token-sys": {
                "enabled": True,
                "pii_types": "all",
                "mask_style": "token",
                "unmask": True,
                "api_key_sha256": _sha(TOKEN_KEY),
            },
            "no-unmask-sys": {
                "enabled": True,
                "pii_types": "all",
                "mask_style": "token",
                "unmask": False,
                "api_key_sha256": _sha(NO_UNMASK_KEY),
            },
            "synthetic-sys": {
                "enabled": True,
                "pii_types": "all",
                "mask_style": "synthetic",
                "unmask": True,
                "api_key_sha256": _sha(SYNTHETIC_KEY),
            },
        },
    }


def _settings(tmp_path, **overrides) -> Settings:
    settings = make_settings(
        tmp_path,
        recognizer_modules=[
            "pii_guard.recognizers.numeric",
            "pii_guard.recognizers.documents",
            "pii_guard.recognizers.dates",
            "pii_guard.recognizers.names",
            "pii_guard.recognizers.address",
            "pii_guard.recognizers.civil",
            "pii_guard.recognizers.standalone",
        ],
        **overrides,
    )
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
        yield app, c


def _chat(messages: list[dict]) -> dict:
    return {"messages": messages}


@pytest.mark.asyncio
async def test_chat_token_unmask_roundtrip(tmp_path) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as (_app, client):
        content = "Клиент Иванов Иван Иванович, телефон +7 916 123-45-67"
        resp = await client.post(
            CHAT_PATH,
            json=_chat([{"role": "user", "content": content}]),
            headers={"X-API-Key": TOKEN_KEY},
        )
        assert resp.status_code == 200
        body = resp.json()
        masked = body["pii_guard"]["masked_messages"][0]["content"]
        assert IVANOV not in masked
        assert "916" not in masked
        answer = body["choices"][0]["message"]["content"]
        assert IVANOV_FULL in answer
        assert PHONE_PLAIN in answer


@pytest.mark.asyncio
async def test_chat_synthetic_unmask_roundtrip(tmp_path) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as (_app, client):
        content = "Клиент Иванов Иван Иванович, телефон +7 916 123-45-67"
        resp = await client.post(
            CHAT_PATH,
            json=_chat([{"role": "user", "content": content}]),
            headers={"X-API-Key": SYNTHETIC_KEY},
        )
        assert resp.status_code == 200
        body = resp.json()
        masked = body["pii_guard"]["masked_messages"][0]["content"]
        assert IVANOV_FULL not in masked
        assert PHONE_PLAIN not in masked
        assert body["pii_guard"]["recheck_masked"] == 0
        answer = body["choices"][0]["message"]["content"]
        assert IVANOV_FULL in answer
        assert PHONE_PLAIN in answer


@pytest.mark.asyncio
async def test_chat_same_token_across_messages(tmp_path) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as (_app, client):
        resp = await client.post(
            CHAT_PATH,
            json=_chat(
                [
                    {"role": "user", "content": IVANOV_FULL},
                    {"role": "user", "content": IVANOV_FULL},
                ]
            ),
            headers={"X-API-Key": TOKEN_KEY},
        )
        assert resp.status_code == 200
        masked = resp.json()["pii_guard"]["masked_messages"]
        assert masked[0]["content"] == masked[1]["content"]
        assert IVANOV not in masked[0]["content"]


@pytest.mark.asyncio
async def test_chat_unmask_disabled_keeps_masks(tmp_path) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as (_app, client):
        resp = await client.post(
            CHAT_PATH,
            json=_chat([{"role": "user", "content": IVANOV_FULL}]),
            headers={"X-API-Key": NO_UNMASK_KEY},
        )
        assert resp.status_code == 200
        answer = resp.json()["choices"][0]["message"]["content"]
        assert IVANOV not in answer
        assert "[ФИО_1]" in answer


@pytest.mark.asyncio
async def test_chat_stream_not_supported(tmp_path) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as (_app, client):
        resp = await client.post(
            CHAT_PATH,
            json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
            headers={"X-API-Key": TOKEN_KEY},
        )
        assert resp.status_code == 400
        assert resp.json() == {"error": "streaming_not_supported"}


@pytest.mark.asyncio
async def test_chat_missing_api_key(tmp_path) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as (_app, client):
        resp = await client.post(
            CHAT_PATH,
            json=_chat([{"role": "user", "content": "hi"}]),
        )
        assert resp.status_code == 401
        assert resp.json() == {"error": "missing_api_key"}


class FailingLLM:
    name = "failing"

    async def complete(self, messages: list[dict[str, str]]) -> str:
        raise LLMError("boom")

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_chat_llm_failure_falls_back_to_mock(tmp_path) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as (app, client):
        app.state.llm_client = FailingLLM()
        resp = await client.post(
            CHAT_PATH,
            json=_chat([{"role": "user", "content": IVANOV_FULL}]),
            headers={"X-API-Key": TOKEN_KEY},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pii_guard"]["llm"] == "mock_fallback"
        assert IVANOV_FULL in body["choices"][0]["message"]["content"]


@pytest.mark.asyncio
async def test_chat_overloaded_returns_429(tmp_path) -> None:
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
            CHAT_PATH,
            json=_chat([{"role": "user", "content": "hi"}]),
            headers={"X-API-Key": TOKEN_KEY},
        )
        assert resp.status_code == 429
        assert resp.json() == {"error": "overloaded"}
        assert resp.headers["retry-after"] == "1"
        gate.exit()

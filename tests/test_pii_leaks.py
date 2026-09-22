from __future__ import annotations

import hashlib
import json
import secrets
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from pii_guard.llm.client import LLMError
from pii_guard.main import create_app
from pii_guard.settings import Settings
from tests.helpers import make_settings, write_config

TOKEN_KEY = secrets.token_urlsafe(16)

FIO = "Иванов Иван Иванович"
PASSPORT = "4509 123456"
PHONE = "+7 916 123-45-67"
EMAIL = "ivanov@mail.ru"
INN = "500100732259"
BIRTH_DATE = "12.03.1985"
PII_VALUES = [FIO, PASSPORT, PHONE, EMAIL, INN, BIRTH_DATE]

REQUEST_TEXT = (
    f"Клиент {FIO}, паспорт {PASSPORT}, телефон {PHONE}, "
    f"email {EMAIL}, ИНН {INN}, дата рождения {BIRTH_DATE}"
)


def _sha(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _systems_config() -> dict:
    return {
        "defaults": {"mask_style": "partial", "unmask": True, "strict": False},
        "systems": {
            "checker": {
                "enabled": True,
                "pii_types": "all",
                "mask_style": "full",
            },
            "token-sys": {
                "enabled": True,
                "pii_types": "all",
                "mask_style": "token",
                "unmask": True,
                "api_key_sha256": _sha(TOKEN_KEY),
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
        log_level="DEBUG",
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


def _capture(capsys) -> tuple[str, str, list[str]]:
    captured = capsys.readouterr()
    events: list[str] = []
    for line in captured.out.splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "event" in data:
            events.append(data["event"])
    return captured.out, captured.err, events


def _assert_no_pii(out: str, err: str) -> None:
    for value in PII_VALUES:
        assert value not in out
        assert value not in err


async def _assert_no_pii_in_metrics(client: AsyncClient) -> None:
    resp = await client.get("/metrics")
    body = resp.text
    for value in PII_VALUES:
        assert value not in body


@pytest.mark.asyncio
async def test_process_flow_no_pii_leak(tmp_path, capsys) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as (_app, client):
        payload_id = "p1"

        resp = await client.post(
            "/process", json={"payload": REQUEST_TEXT, "payload_id": payload_id}
        )
        assert resp.status_code == 200
        masked = resp.json()["result"]
        assert all(value not in masked for value in PII_VALUES)

        resp = await client.post(
            "/process", json={"payload": REQUEST_TEXT, "payload_id": payload_id}
        )
        assert resp.status_code == 200
        assert resp.json()["result"] == masked

        resp = await client.post("/process", json={"payload": masked, "payload_id": payload_id})
        assert resp.status_code == 200
        assert resp.json()["result"] == REQUEST_TEXT

        changed = masked + " уточните данные"
        resp = await client.post("/process", json={"payload": changed, "payload_id": payload_id})
        assert resp.status_code == 200

        out, err, events = _capture(capsys)
        assert "process" in events
        _assert_no_pii(out, err)
        await _assert_no_pii_in_metrics(client)


@pytest.mark.asyncio
async def test_mask_unmask_chat_no_pii_leak(tmp_path, capsys) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as (_app, client):
        headers = {"X-API-Key": TOKEN_KEY}

        resp = await client.post("/api/v1/mask", json={"text": REQUEST_TEXT}, headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        session_id = body["session_id"]
        masked = body["masked_text"]
        assert all(value not in masked for value in PII_VALUES)

        resp = await client.post(
            "/api/v1/unmask",
            json={"session_id": session_id, "text": masked},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["text"] == REQUEST_TEXT

        resp = await client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": REQUEST_TEXT}]},
            headers=headers,
        )
        assert resp.status_code == 200

        out, err, events = _capture(capsys)
        assert "mask" in events
        assert "unmask" in events
        assert "chat" in events
        _assert_no_pii(out, err)
        await _assert_no_pii_in_metrics(client)


@pytest.mark.asyncio
async def test_validation_errors_do_not_echo_input(tmp_path, capsys) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as (_app, client):
        resp = await client.post("/process", json={"fio": FIO, "payload_id": "x"})
        assert resp.status_code == 422
        assert all(value not in resp.text for value in PII_VALUES)

        broken = f'{{"payload": "Клиент {FIO}, паспорт {PASSPORT}", "payload_id": "x"'
        resp = await client.post(
            "/process", content=broken, headers={"content-type": "application/json"}
        )
        assert resp.status_code == 400
        assert all(value not in resp.text for value in PII_VALUES)

        resp = await client.post("/process", json={"payload": REQUEST_TEXT})
        assert resp.status_code == 422
        assert all(value not in resp.text for value in PII_VALUES)

        out, err, events = _capture(capsys)
        assert "invalid_request" in events
        _assert_no_pii(out, err)


@pytest.mark.asyncio
async def test_internal_error_does_not_leak_pii(tmp_path, capsys) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as (app, client):

        async def _boom(payload_id: str, payload: str):
            raise RuntimeError(f"boom {FIO} {PASSPORT}")

        app.state.process_service.handle = _boom

        resp = await client.post("/process", json={"payload": REQUEST_TEXT, "payload_id": "p1"})
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"] == "internal_error"
        assert all(value not in resp.text for value in PII_VALUES)

        out, err, events = _capture(capsys)
        assert "unhandled_exception" in events
        _assert_no_pii(out, err)


class FailingLLM:
    name = "failing"

    async def complete(self, messages: list[dict[str, str]]) -> str:
        raise LLMError(f"LLM failed for {FIO}")

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_llm_failure_does_not_leak_pii(tmp_path, capsys) -> None:
    settings = _settings(tmp_path)
    async with _client_for(settings) as (app, client):
        app.state.llm_client = FailingLLM()

        resp = await client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": REQUEST_TEXT}]},
            headers={"X-API-Key": TOKEN_KEY},
        )
        assert resp.status_code == 200
        assert resp.json()["pii_guard"]["llm"] == "mock_fallback"

        out, err, events = _capture(capsys)
        assert "llm_fallback" in events
        _assert_no_pii(out, err)

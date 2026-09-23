from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from pii_guard.main import create_app
from pii_guard.settings import Settings
from tests.helpers import make_settings


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
async def test_metrics_after_process(tmp_path) -> None:
    settings = make_settings(tmp_path)
    async with _client_for(settings) as client:
        text = "email ivanov@mail.ru"
        resp = await client.post("/process", json={"payload": text, "payload_id": "m-1"})
        assert resp.status_code == 200

        metrics = await client.get("/metrics")
        assert metrics.status_code == 200
        body = metrics.text

        assert 'pii_requests_total{endpoint="/process",status="200"}' in body
        assert 'pii_request_duration_seconds_bucket{endpoint="/process"' in body
        assert 'pii_tokens_total{endpoint="/process"}' in body
        assert 'pii_entities_total{pii_type="EMAIL",system="checker"}' in body
        assert "ivanov@mail.ru" not in body


@pytest.mark.asyncio
async def test_unknown_path_endpoint_other(tmp_path) -> None:
    settings = make_settings(tmp_path)
    async with _client_for(settings) as client:
        resp = await client.get("/some/unknown/path")
        assert resp.status_code == 404

        metrics = await client.get("/metrics")
        assert metrics.status_code == 200
        body = metrics.text
        assert 'pii_requests_total{endpoint="other",status="404"}' in body


def test_multiproc_metrics_single_occurrence(tmp_path, monkeypatch) -> None:
    from prometheus_client import Counter, generate_latest

    from pii_guard.observability.metrics import _build_registries

    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
    served, metrics_registry = _build_registries()
    assert served is not metrics_registry
    Counter("test_counter", "test", registry=metrics_registry).inc()
    assert b"test_counter" not in generate_latest(served)


def test_multiproc_metrics_single_registry(monkeypatch) -> None:
    from pii_guard.observability.metrics import _build_registries

    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    served, metrics_registry = _build_registries()
    assert served is metrics_registry

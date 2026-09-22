import pytest

PAYLOAD_MARKER = "СЕКРЕТНЫЕ_ДАННЫЕ_12345"


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready(client):
    resp = await client.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_process_valid(client):
    resp = await client.post(
        "/process",
        json={"payload": PAYLOAD_MARKER, "payload_id": "id-1"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"result": PAYLOAD_MARKER}


@pytest.mark.asyncio
async def test_process_missing_payload_id(client):
    resp = await client.post("/process", json={"payload": PAYLOAD_MARKER})
    assert resp.status_code == 422
    assert PAYLOAD_MARKER not in resp.text


@pytest.mark.asyncio
async def test_process_bad_json(client):
    resp = await client.post(
        "/process",
        content=b'{"payload": "' + PAYLOAD_MARKER.encode() + b'",',
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 400
    assert PAYLOAD_MARKER not in resp.text


@pytest.mark.asyncio
async def test_process_payload_too_large(client):
    big = "x" * 2000
    resp = await client.post(
        "/process",
        content=b'{"payload": "' + big.encode() + b'", "payload_id": "id-2"}',
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 413
    assert resp.json() == {"error": "payload_too_large"}


@pytest.mark.asyncio
async def test_request_id_generated(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("x-request-id")


@pytest.mark.asyncio
async def test_request_id_passthrough(client):
    resp = await client.get("/health", headers={"X-Request-ID": "my-custom-id"})
    assert resp.status_code == 200
    assert resp.headers.get("x-request-id") == "my-custom-id"

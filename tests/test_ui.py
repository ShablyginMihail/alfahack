from httpx import ASGITransport, AsyncClient

from pii_guard.main import create_app
from tests.helpers import make_settings


async def test_index_page_served_with_security_headers(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "PII Guard" in resp.text
    assert "default-src 'self'" in resp.headers["content-security-policy"]
    assert resp.headers["x-content-type-options"] == "nosniff"


async def test_static_assets_served(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for path in ("/static/app.js", "/static/style.css"):
            resp = await client.get(path)
            assert resp.status_code == 200, path


async def test_static_does_not_expose_other_files(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/static/../pyproject.toml")
    assert resp.status_code == 404

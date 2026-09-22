import pytest
from httpx import ASGITransport, AsyncClient

from pii_guard.main import create_app
from pii_guard.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        redis_url=None,
        max_body_bytes=1000,
        log_level="WARNING",
    )


@pytest.fixture
async def client(settings: Settings):
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as c,
    ):
        yield c

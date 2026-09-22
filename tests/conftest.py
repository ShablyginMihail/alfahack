import pytest
from httpx import ASGITransport, AsyncClient

from pii_guard.main import create_app
from pii_guard.settings import Settings
from tests.helpers import make_settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
async def client(settings: Settings):
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as c,
    ):
        yield c

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.ai_engine_adapter import venue_registry


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset the in-memory venue registry before and after every test."""
    venue_registry.clear_all()
    yield
    venue_registry.clear_all()


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

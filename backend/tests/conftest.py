import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

_AI_ENGINE_DIR = os.path.normpath(os.path.join(_BACKEND_DIR, "..", "ai-engine"))
if _AI_ENGINE_DIR not in sys.path:
    sys.path.insert(0, _AI_ENGINE_DIR)

import pytest
from httpx import AsyncClient, ASGITransport
from mongomock_motor import AsyncMongoMockClient
from app.main import app
from app.services.ai_engine_adapter import venue_registry
from app.database.mongodb.connection import db_connection


@pytest.fixture(autouse=True)
async def setup_test_environment():
    """
    Autouse fixture that sets up an isolated in-memory MongoMock database
    and clears in-memory venue registry before and after every test.
    """
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["crowdos_test_db"]
    db_connection.client = mock_client
    db_connection.db = mock_db
    db_connection._is_healthy = True

    venue_registry.clear_all()

    yield

    venue_registry.clear_all()
    db_connection.client = None
    db_connection.db = None
    db_connection._is_healthy = False


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

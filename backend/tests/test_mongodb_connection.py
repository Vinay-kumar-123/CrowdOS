"""
Sprint 10 — MongoDB Connection Lifecycle & Configuration Tests.
"""
import pytest
from app.database.mongodb.connection import (
    MongoDBConnection,
    mask_mongodb_uri,
    connect_to_mongo,
    close_mongo_connection,
    db_connection,
)
from app.database.mongodb.indexes import create_all_indexes, INDEX_SPECIFICATIONS
from mongomock_motor import AsyncMongoMockClient


def test_mask_mongodb_uri():
    """Verify passwords in MongoDB URIs are masked for logging."""
    uri_with_auth = "mongodb://admin:superSecretPass123@localhost:27017/crowdos_db?authSource=admin"
    masked = mask_mongodb_uri(uri_with_auth)
    assert "superSecretPass123" not in masked
    assert "mongodb://admin:***@localhost:27017/crowdos_db?authSource=admin" == masked

    uri_no_auth = "mongodb://localhost:27017/crowdos_db"
    assert mask_mongodb_uri(uri_no_auth) == uri_no_auth
    assert mask_mongodb_uri("") == ""


@pytest.mark.asyncio
async def test_connection_lifecycle():
    """Verify connection lifecycle methods."""
    conn = MongoDBConnection()
    assert not conn.is_connected
    assert conn.get_database() is None
    assert conn.get_collection("venues") is None

    # Attach mock
    mock_client = AsyncMongoMockClient()
    conn.client = mock_client
    conn.db = mock_client["test_crowdos"]
    conn._is_healthy = True

    assert conn.is_connected
    assert conn.get_database() is not None
    assert conn.get_collection("venues") is not None


@pytest.mark.asyncio
async def test_index_specifications_and_creation():
    """Verify all collection indexes can be created idempotently."""
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["test_index_db"]

    # Verify specs exist for all defined collections
    expected_collections = {
        "venues",
        "sessions",
        "events",
        "alerts",
        "predictions",
        "visitors",
        "visitor_events",
        "visits",
        "users",
    }
    assert set(INDEX_SPECIFICATIONS.keys()) == expected_collections

    results = await create_all_indexes(mock_db)
    assert len(results) == len(expected_collections)
    for coll_name in expected_collections:
        assert coll_name in results


@pytest.mark.asyncio
async def test_index_creation_none_db():
    """Verify index creation handles None db gracefully."""
    results = await create_all_indexes(None)
    assert results == {}

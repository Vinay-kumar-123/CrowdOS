"""
Sprint 10 — Database Failure & Degraded Mode Tests.

Verifies that when MongoDB connection is completely unavailable:
1. Live AI Engine continues normal in-memory computation.
2. FastAPI endpoints return 200/201 without unhandled 500 crashes.
3. System status correctly reports database_connected = False.
"""
import pytest
from app.database.mongodb.connection import db_connection


@pytest.mark.asyncio
async def test_api_works_when_mongodb_is_down(async_client):
    """Simulate MongoDB outage by setting db_connection.client and db to None."""
    # Force MongoDB down
    db_connection.client = None
    db_connection.db = None
    db_connection._is_healthy = False

    venue_id = "degraded_venue_10"

    # Status endpoint reports database disconnected
    status_res = await async_client.get("/api/status")
    assert status_res.status_code == 200
    assert status_res.json()["database_connected"] is False

    # 1. Create Session in Degraded Mode
    create_res = await async_client.post(
        f"/api/v1/venues/{venue_id}/sessions",
        json={"venue_capacity": 1000},
    )
    assert create_res.status_code == 201
    session_id = create_res.json()["session_id"]
    assert create_res.json()["status"] == "CREATED"

    # 2. Start Session in Degraded Mode
    start_res = await async_client.post(f"/api/v1/venues/{venue_id}/sessions/{session_id}/start")
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "ACTIVE"

    # 3. Ingest Event in Degraded Mode
    event_res = await async_client.post(
        f"/api/v1/venues/{venue_id}/sessions/{session_id}/events",
        json={"event_type": "ENTRY", "gate_id": "gate_deg_1"},
    )
    assert event_res.status_code == 200
    assert event_res.json()["status"] == "processed"

    # 4. Intelligence queries work in Degraded Mode
    intel_res = await async_client.get(f"/api/v1/venues/{venue_id}/intelligence")
    assert intel_res.status_code == 200
    assert intel_res.json()["occupancy"]["total_entries"] == 1

    # 5. Prediction queries work in Degraded Mode
    pred_res = await async_client.get(f"/api/v1/venues/{venue_id}/predictions")
    assert pred_res.status_code == 200
    assert pred_res.json()["venue_id"] == venue_id

    # 6. Stop Session in Degraded Mode
    stop_res = await async_client.post(f"/api/v1/venues/{venue_id}/sessions/{session_id}/stop")
    assert stop_res.status_code == 200
    assert stop_res.json()["session_id"] == session_id

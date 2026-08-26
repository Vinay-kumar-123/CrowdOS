"""
Sprint 10 — End-to-End API Persistence Integration Tests.

Verifies that FastAPI REST endpoints properly persist venues, sessions,
events, alerts, and predictions into MongoDB.
"""
import pytest
from app.database.mongodb.connection import db_connection


@pytest.mark.asyncio
async def test_venue_persistence_integration(async_client):
    """Verify venue registration persists to MongoDB."""
    # Create session which registers venue
    res = await async_client.post(
        "/api/v1/venues/stadium_a/sessions",
        json={"venue_capacity": 5000, "metadata": {"city": "Metropolis"}},
    )
    assert res.status_code == 201

    # Verify venue in MongoDB
    venue_doc = await db_connection.db["venues"].find_one({"venue_id": "stadium_a"})
    assert venue_doc is not None
    assert venue_doc["capacity"] == 5000


@pytest.mark.asyncio
async def test_session_lifecycle_persistence(async_client):
    """Verify full session state transition cycle persists to MongoDB."""
    venue_id = "stadium_b"

    # 1. Create Session
    create_res = await async_client.post(
        f"/api/v1/venues/{venue_id}/sessions",
        json={"venue_capacity": 1000},
    )
    assert create_res.status_code == 201
    session_id = create_res.json()["session_id"]

    # Verify CREATED in MongoDB
    doc = await db_connection.db["sessions"].find_one({"session_id": session_id})
    assert doc is not None
    assert doc["status"] == "CREATED"

    # 2. Start Session
    start_res = await async_client.post(f"/api/v1/venues/{venue_id}/sessions/{session_id}/start")
    assert start_res.status_code == 200

    doc = await db_connection.db["sessions"].find_one({"session_id": session_id})
    assert doc["status"] == "ACTIVE"
    assert doc.get("started_at") is not None

    # 3. Pause Session
    pause_res = await async_client.post(f"/api/v1/venues/{venue_id}/sessions/{session_id}/pause")
    assert pause_res.status_code == 200

    doc = await db_connection.db["sessions"].find_one({"session_id": session_id})
    assert doc["status"] == "PAUSED"
    assert doc.get("paused_at") is not None

    # 4. Resume Session
    resume_res = await async_client.post(f"/api/v1/venues/{venue_id}/sessions/{session_id}/resume")
    assert resume_res.status_code == 200

    doc = await db_connection.db["sessions"].find_one({"session_id": session_id})
    assert doc["status"] == "ACTIVE"
    assert doc.get("resumed_at") is not None

    # 5. Stop Session
    stop_res = await async_client.post(f"/api/v1/venues/{venue_id}/sessions/{session_id}/stop")
    assert stop_res.status_code == 200

    doc = await db_connection.db["sessions"].find_one({"session_id": session_id})
    assert doc["status"] == "STOPPED"
    assert doc.get("stopped_at") is not None
    assert doc.get("summary") is not None


@pytest.mark.asyncio
async def test_event_persistence_and_duplicate_handling(async_client):
    """Verify event ingest persists operational records and duplicate events are safely handled."""
    venue_id = "stadium_c"

    # Setup session
    sess_res = await async_client.post(
        f"/api/v1/venues/{venue_id}/sessions",
        json={"venue_capacity": 1000},
    )
    session_id = sess_res.json()["session_id"]
    await async_client.post(f"/api/v1/venues/{venue_id}/sessions/{session_id}/start")

    # Ingest event 1
    ev_res1 = await async_client.post(
        f"/api/v1/venues/{venue_id}/sessions/{session_id}/events",
        json={
            "event_type": "ENTRY",
            "gate_id": "gate_1",
            "event_id": "ev_unique_101",
        },
    )
    assert ev_res1.status_code == 200
    assert ev_res1.json()["status"] == "processed"

    # Verify event in MongoDB
    ev_doc = await db_connection.db["events"].find_one({"event_id": "ev_unique_101"})
    assert ev_doc is not None
    assert ev_doc["gate_id"] == "gate_1"
    assert ev_doc["event_type"] == "ENTRY"

    # Ingest duplicate event
    ev_res_dup = await async_client.post(
        f"/api/v1/venues/{venue_id}/sessions/{session_id}/events",
        json={
            "event_type": "ENTRY",
            "gate_id": "gate_1",
            "event_id": "ev_unique_101",
        },
    )
    assert ev_res_dup.status_code == 200
    assert ev_res_dup.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_prediction_persistence_and_history_endpoint(async_client):
    """Verify predictions are persisted and retrievable via /history endpoint."""
    venue_id = "stadium_d"

    # Setup session
    sess_res = await async_client.post(
        f"/api/v1/venues/{venue_id}/sessions",
        json={"venue_capacity": 1000},
    )
    session_id = sess_res.json()["session_id"]
    await async_client.post(f"/api/v1/venues/{venue_id}/sessions/{session_id}/start")

    # Trigger prediction
    pred_res = await async_client.get(f"/api/v1/venues/{venue_id}/predictions")
    assert pred_res.status_code == 200
    data = pred_res.json()
    assert data["venue_id"] == venue_id

    # Verify prediction persisted in MongoDB
    pred_docs = await db_connection.db["predictions"].find({"venue_id": venue_id}).to_list(10)
    assert len(pred_docs) >= 1

    # Query history endpoint
    hist_res = await async_client.get(f"/api/v1/venues/{venue_id}/predictions/history")
    assert hist_res.status_code == 200
    history = hist_res.json()
    assert len(history) >= 1
    assert history[0]["venue_id"] == venue_id

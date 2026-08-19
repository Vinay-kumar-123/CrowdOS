import pytest


@pytest.mark.asyncio
async def test_event_ingest_entry_and_exit(async_client):
    # Setup session
    res = await async_client.post("/api/v1/venues/arena_events/sessions", json={"venue_capacity": 500})
    session_id = res.json()["session_id"]
    await async_client.post(f"/api/v1/venues/arena_events/sessions/{session_id}/start")

    # Ingest ENTRY
    entry_payload = {
        "event_type": "ENTRY",
        "gate_id": "gate_north",
        "event_id": "evt_001",
    }
    resp = await async_client.post(
        f"/api/v1/venues/arena_events/sessions/{session_id}/events",
        json=entry_payload,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "processed"
    assert data["event_type"] == "ENTRY"
    assert data["gate_id"] == "gate_north"

    # Ingest EXIT with dwell
    exit_payload = {
        "event_type": "EXIT",
        "gate_id": "gate_north",
        "event_id": "evt_002",
        "dwell_time": 45.5,
    }
    resp_exit = await async_client.post(
        f"/api/v1/venues/arena_events/sessions/{session_id}/events",
        json=exit_payload,
    )
    assert resp_exit.status_code == 200
    assert resp_exit.json()["status"] == "processed"
    assert resp_exit.json()["event_type"] == "EXIT"


@pytest.mark.asyncio
async def test_event_ingest_duplicate_suppression(async_client):
    # Setup session
    res = await async_client.post("/api/v1/venues/arena_dup/sessions", json={"venue_capacity": 500})
    session_id = res.json()["session_id"]
    await async_client.post(f"/api/v1/venues/arena_dup/sessions/{session_id}/start")

    payload = {
        "event_type": "ENTRY",
        "gate_id": "gate_1",
        "event_id": "evt_unique_100",
    }
    r1 = await async_client.post(
        f"/api/v1/venues/arena_dup/sessions/{session_id}/events", json=payload
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "processed"

    # Duplicate should be ignored
    r2 = await async_client.post(
        f"/api/v1/venues/arena_dup/sessions/{session_id}/events", json=payload
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_event_ingest_validation(async_client):
    # Setup session
    res = await async_client.post("/api/v1/venues/arena_val/sessions", json={"venue_capacity": 500})
    session_id = res.json()["session_id"]
    await async_client.post(f"/api/v1/venues/arena_val/sessions/{session_id}/start")

    # Invalid event_type
    bad_type = await async_client.post(
        f"/api/v1/venues/arena_val/sessions/{session_id}/events",
        json={"event_type": "INVALID_MOVE", "gate_id": "gate_1"},
    )
    assert bad_type.status_code == 422

    # Non-existent session
    bad_session = await async_client.post(
        "/api/v1/venues/arena_val/sessions/non_existent_session/events",
        json={"event_type": "ENTRY", "gate_id": "gate_1"},
    )
    assert bad_session.status_code == 404

import pytest
import time


@pytest.mark.asyncio
async def test_create_session(async_client):
    payload = {
        "venue_capacity": 500,
        "metadata": {"operator": "admin", "event": "Concert A"}
    }
    response = await async_client.post("/api/v1/venues/stadium_1/sessions", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["venue_id"] == "stadium_1"
    assert data["status"] == "CREATED"
    assert data["metadata"]["operator"] == "admin"
    assert "session_id" in data


@pytest.mark.asyncio
async def test_list_and_get_session(async_client):
    # Create session
    res = await async_client.post("/api/v1/venues/arena_1/sessions", json={"venue_capacity": 1000})
    assert res.status_code == 201
    session_id = res.json()["session_id"]

    # List sessions
    list_res = await async_client.get("/api/v1/venues/arena_1/sessions")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == 1
    assert list_data["sessions"][0]["session_id"] == session_id

    # Get single session
    get_res = await async_client.get(f"/api/v1/venues/arena_1/sessions/{session_id}")
    assert get_res.status_code == 200
    assert get_res.json()["session_id"] == session_id

    # Get non-existent session
    not_found = await async_client.get("/api/v1/venues/arena_1/sessions/non_existent_id")
    assert not_found.status_code == 404


@pytest.mark.asyncio
async def test_session_lifecycle_transitions(async_client):
    # Create
    res = await async_client.post("/api/v1/venues/hall_1/sessions", json={"venue_capacity": 300})
    session_id = res.json()["session_id"]

    # Active session before start should be null
    active_res = await async_client.get("/api/v1/venues/hall_1/sessions/active")
    assert active_res.status_code == 200
    assert active_res.json() is None

    # Start
    start_res = await async_client.post(f"/api/v1/venues/hall_1/sessions/{session_id}/start")
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "ACTIVE"

    # Active session check
    active_res2 = await async_client.get("/api/v1/venues/hall_1/sessions/active")
    assert active_res2.status_code == 200
    assert active_res2.json()["session_id"] == session_id

    # Pause
    pause_res = await async_client.post(f"/api/v1/venues/hall_1/sessions/{session_id}/pause")
    assert pause_res.status_code == 200
    assert pause_res.json()["status"] == "PAUSED"

    # Resume
    resume_res = await async_client.post(f"/api/v1/venues/hall_1/sessions/{session_id}/resume")
    assert resume_res.status_code == 200
    assert resume_res.json()["status"] == "ACTIVE"

    # Stop -> returns summary
    stop_res = await async_client.post(f"/api/v1/venues/hall_1/sessions/{session_id}/stop")
    assert stop_res.status_code == 200
    summary = stop_res.json()
    assert summary["session_id"] == session_id
    assert summary["venue_id"] == "hall_1"
    assert "duration_seconds" in summary
    assert "total_entries" in summary
    assert "peak_occupancy" in summary


@pytest.mark.asyncio
async def test_invalid_state_transitions(async_client):
    res = await async_client.post("/api/v1/venues/hall_2/sessions", json={"venue_capacity": 300})
    session_id = res.json()["session_id"]

    # Cannot pause a CREATED session
    pause_res = await async_client.post(f"/api/v1/venues/hall_2/sessions/{session_id}/pause")
    assert pause_res.status_code == 409

    # Start it
    await async_client.post(f"/api/v1/venues/hall_2/sessions/{session_id}/start")

    # Stop it
    await async_client.post(f"/api/v1/venues/hall_2/sessions/{session_id}/stop")

    # Cannot start a STOPPED session (terminal state)
    start_again = await async_client.post(f"/api/v1/venues/hall_2/sessions/{session_id}/start")
    assert start_again.status_code == 409


@pytest.mark.asyncio
async def test_session_expiration(async_client):
    res = await async_client.post("/api/v1/venues/hall_exp/sessions", json={"venue_capacity": 300})
    session_id = res.json()["session_id"]
    await async_client.post(f"/api/v1/venues/hall_exp/sessions/{session_id}/start")

    # Future epoch far beyond max_duration_seconds (86400s)
    future_epoch = time.time() + 100000.0
    exp_res = await async_client.post(
        f"/api/v1/venues/hall_exp/sessions/check-expirations?now_epoch={future_epoch}"
    )
    assert exp_res.status_code == 200
    data = exp_res.json()
    assert data["expired_count"] == 1
    assert session_id in data["expired_session_ids"]

    # Check status is now EXPIRED
    session_res = await async_client.get(f"/api/v1/venues/hall_exp/sessions/{session_id}")
    assert session_res.status_code == 200
    assert session_res.json()["status"] == "EXPIRED"

import pytest


@pytest.mark.asyncio
async def test_validation_negative_capacity(async_client):
    # Negative capacity should fail Pydantic validation (ge=0)
    res = await async_client.post(
        "/api/v1/venues/val_venue/sessions", json={"venue_capacity": -100}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_validation_event_negative_dwell(async_client):
    # Setup session
    res = await async_client.post(
        "/api/v1/venues/val_venue_2/sessions", json={"venue_capacity": 500}
    )
    session_id = res.json()["session_id"]
    await async_client.post(f"/api/v1/venues/val_venue_2/sessions/{session_id}/start")

    # Negative dwell_time -> 422
    bad_dwell = await async_client.post(
        f"/api/v1/venues/val_venue_2/sessions/{session_id}/events",
        json={"event_type": "EXIT", "gate_id": "gate_1", "dwell_time": -10.0},
    )
    assert bad_dwell.status_code == 422


@pytest.mark.asyncio
async def test_validation_missing_required_fields(async_client):
    # Setup session
    res = await async_client.post(
        "/api/v1/venues/val_venue_3/sessions", json={"venue_capacity": 500}
    )
    session_id = res.json()["session_id"]

    # Missing event_type and gate_id -> 422
    bad_req = await async_client.post(
        f"/api/v1/venues/val_venue_3/sessions/{session_id}/events",
        json={},
    )
    assert bad_req.status_code == 422


@pytest.mark.asyncio
async def test_validation_404_responses(async_client):
    # Non-existent venue
    res1 = await async_client.get("/api/v1/venues/unknown_123/sessions")
    assert res1.status_code == 404

    # Non-existent intelligence
    res2 = await async_client.get("/api/v1/venues/unknown_123/intelligence")
    assert res2.status_code == 404

    # Non-existent predictions
    res3 = await async_client.get("/api/v1/venues/unknown_123/predictions")
    assert res3.status_code == 404

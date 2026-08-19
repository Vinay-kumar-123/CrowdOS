import pytest


@pytest.mark.asyncio
async def test_alerts_endpoints(async_client):
    # Setup session
    res = await async_client.post("/api/v1/venues/alerts_venue/sessions", json={"venue_capacity": 500})
    session_id = res.json()["session_id"]
    await async_client.post(f"/api/v1/venues/alerts_venue/sessions/{session_id}/start")

    # Get all alerts
    all_res = await async_client.get("/api/v1/venues/alerts_venue/alerts")
    assert all_res.status_code == 200
    all_data = all_res.json()
    assert all_data["venue_id"] == "alerts_venue"
    assert isinstance(all_data["alerts"], list)
    assert all_data["total"] >= 0

    # Get active alerts
    active_res = await async_client.get("/api/v1/venues/alerts_venue/alerts/active")
    assert active_res.status_code == 200
    active_data = active_res.json()
    assert active_data["venue_id"] == "alerts_venue"
    assert isinstance(active_data["alerts"], list)

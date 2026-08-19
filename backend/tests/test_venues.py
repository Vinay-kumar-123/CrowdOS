import pytest


@pytest.mark.asyncio
async def test_venues_endpoints(async_client):
    # Before initializing any venue
    res = await async_client.get("/api/v1/venues")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # Initialize a venue via session creation
    s_res = await async_client.post(
        "/api/v1/venues/venue_test_1/sessions", json={"venue_capacity": 800}
    )
    assert s_res.status_code == 201

    # Check venue list
    list_res = await async_client.get("/api/v1/venues")
    assert list_res.status_code == 200
    assert "venue_test_1" in list_res.json()

    # Get venue info
    info_res = await async_client.get("/api/v1/venues/venue_test_1")
    assert info_res.status_code == 200
    info = info_res.json()
    assert info["venue_id"] == "venue_test_1"
    assert info["venue_capacity"] == 800

    # Get non-existent venue info -> 404
    bad_info = await async_client.get("/api/v1/venues/unknown_venue")
    assert bad_info.status_code == 404

    # Reset venue
    reset_res = await async_client.post("/api/v1/venues/venue_test_1/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["reset"] is True

    # After reset, venue is no longer registered
    info_after = await async_client.get("/api/v1/venues/venue_test_1")
    assert info_after.status_code == 404

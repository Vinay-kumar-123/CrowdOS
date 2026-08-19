import pytest
import asyncio


@pytest.mark.asyncio
async def test_concurrent_session_and_event_ingestion(async_client):
    # Concurrently initialize 5 different venues with sessions
    async def init_venue(v_idx: int):
        venue_id = f"concurrent_venue_{v_idx}"
        res = await async_client.post(
            f"/api/v1/venues/{venue_id}/sessions",
            json={"venue_capacity": 500 + v_idx * 100}
        )
        assert res.status_code == 201
        session_id = res.json()["session_id"]
        start_res = await async_client.post(
            f"/api/v1/venues/{venue_id}/sessions/{session_id}/start"
        )
        assert start_res.status_code == 200

        # Concurrently ingest 10 events
        for e_idx in range(10):
            e_res = await async_client.post(
                f"/api/v1/venues/{venue_id}/sessions/{session_id}/events",
                json={
                    "event_type": "ENTRY" if e_idx % 2 == 0 else "EXIT",
                    "gate_id": f"gate_{e_idx % 3}",
                    "event_id": f"evt_{v_idx}_{e_idx}",
                }
            )
            assert e_res.status_code == 200

        # Concurrently query intelligence and dashboard
        intel_res = await async_client.get(f"/api/v1/venues/{venue_id}/intelligence")
        assert intel_res.status_code == 200

        dash_res = await async_client.get(f"/api/v1/sessions/{session_id}/dashboard")
        assert dash_res.status_code == 200
        assert dash_res.json()["session_id"] == session_id

    # Run all 5 venue tasks concurrently
    tasks = [init_venue(i) for i in range(5)]
    await asyncio.gather(*tasks)

    # Verify venue registry state is clean and contains all 5 venues
    venues_res = await async_client.get("/api/v1/venues")
    assert venues_res.status_code == 200
    registered = venues_res.json()
    for i in range(5):
        assert f"concurrent_venue_{i}" in registered

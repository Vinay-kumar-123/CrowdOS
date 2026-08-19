import pytest


@pytest.mark.asyncio
async def test_dashboard_snapshot_endpoint(async_client):
    # Setup session
    res = await async_client.post(
        "/api/v1/venues/dash_venue/sessions", json={"venue_capacity": 1000}
    )
    assert res.status_code == 201
    session_id = res.json()["session_id"]
    await async_client.post(f"/api/v1/venues/dash_venue/sessions/{session_id}/start")

    # Ingest 4 entries at gate_A and 1 exit at gate_A
    for i in range(4):
        await async_client.post(
            f"/api/v1/venues/dash_venue/sessions/{session_id}/events",
            json={"event_type": "ENTRY", "gate_id": "gate_A", "event_id": f"d_in_{i}"},
        )
    await async_client.post(
        f"/api/v1/venues/dash_venue/sessions/{session_id}/events",
        json={"event_type": "EXIT", "gate_id": "gate_A", "event_id": "d_out_0", "dwell_time": 60.0},
    )

    # 1. Query dashboard by session_id across venues
    dash_res1 = await async_client.get(f"/api/v1/sessions/{session_id}/dashboard")
    assert dash_res1.status_code == 200
    dash1 = dash_res1.json()

    assert dash1["session_id"] == session_id
    assert dash1["venue_id"] == "dash_venue"
    assert dash1["session_status"] == "ACTIVE"
    assert dash1["venue_capacity"] == 1000
    assert dash1["total_entries"] == 4
    assert dash1["total_exits"] == 1
    assert dash1["net_flow"] == 3
    assert "density_level" in dash1
    assert "congestion_level" in dash1
    assert "active_alerts" in dash1
    assert "active_anomalies" in dash1
    assert "risk_level" in dash1
    assert "risk_score" in dash1
    assert "trend_direction" in dash1
    assert "occupancy_forecast" in dash1
    assert "flow_forecast" in dash1
    assert "recommendations" in dash1
    assert "gate_summaries" in dash1
    assert "gate_A" in dash1["gate_summaries"]
    assert dash1["gate_summaries"]["gate_A"]["cumulative_entries"] == 4
    assert dash1["gate_summaries"]["gate_A"]["cumulative_exits"] == 1

    # 2. Query dashboard scoped by venue_id and session_id
    dash_res2 = await async_client.get(
        f"/api/v1/venues/dash_venue/sessions/{session_id}/dashboard"
    )
    assert dash_res2.status_code == 200
    assert dash_res2.json()["session_id"] == session_id

    # 3. Non-existent session
    not_found = await async_client.get("/api/v1/sessions/non_existent_dash_session/dashboard")
    assert not_found.status_code == 404

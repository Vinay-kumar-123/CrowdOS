import pytest


@pytest.mark.asyncio
async def test_predictions_requires_active_session(async_client):
    # Venue exists but no session started
    await async_client.post("/api/v1/venues/pred_venue_0/sessions", json={"venue_capacity": 500})
    res = await async_client.get("/api/v1/venues/pred_venue_0/predictions")
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_predictions_full_cycle(async_client):
    # Setup active session
    res = await async_client.post("/api/v1/venues/pred_venue_1/sessions", json={"venue_capacity": 500})
    session_id = res.json()["session_id"]
    await async_client.post(f"/api/v1/venues/pred_venue_1/sessions/{session_id}/start")

    # Ingest events to produce flow
    for i in range(10):
        await async_client.post(
            f"/api/v1/venues/pred_venue_1/sessions/{session_id}/events",
            json={"event_type": "ENTRY", "gate_id": "gate_main", "event_id": f"p_e_{i}"},
        )

    # 1. Full prediction
    pred_res = await async_client.get("/api/v1/venues/pred_venue_1/predictions")
    assert pred_res.status_code == 200
    pred = pred_res.json()
    assert pred["venue_id"] == "pred_venue_1"
    assert pred["session_id"] == session_id
    assert pred["status"] in ("ok", "unavailable")

    if pred["status"] == "ok":
        assert pred["venue_risk"] is not None
        assert "risk_level" in pred["venue_risk"]
        assert "score" in pred["venue_risk"]
        assert pred["venue_decision"] is not None
        assert "action" in pred["venue_decision"]
        assert pred["occupancy_forecast"] is not None
        assert pred["flow_forecast"] is not None

    # 2. Risk endpoint
    risk_res = await async_client.get("/api/v1/venues/pred_venue_1/predictions/risk")
    assert risk_res.status_code == 200

    # 3. Decision endpoint
    dec_res = await async_client.get("/api/v1/venues/pred_venue_1/predictions/decision")
    assert dec_res.status_code == 200

    # 4. Forecast endpoints
    occ_f_res = await async_client.get("/api/v1/venues/pred_venue_1/predictions/forecast/occupancy")
    assert occ_f_res.status_code == 200

    flow_f_res = await async_client.get("/api/v1/venues/pred_venue_1/predictions/forecast/flow")
    assert flow_f_res.status_code == 200

    # 5. Metrics endpoint
    metrics_res = await async_client.get("/api/v1/venues/pred_venue_1/predictions/metrics")
    assert metrics_res.status_code == 200

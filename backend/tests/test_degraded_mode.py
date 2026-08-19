import pytest
from app.services.ai_engine_adapter import venue_registry


@pytest.mark.asyncio
async def test_predictions_degraded_when_prediction_engine_fails(async_client, monkeypatch):
    # Setup session
    res = await async_client.post(
        "/api/v1/venues/degraded_venue/sessions", json={"venue_capacity": 500}
    )
    session_id = res.json()["session_id"]
    await async_client.post(f"/api/v1/venues/degraded_venue/sessions/{session_id}/start")

    # Get engines and monkeypatch predict to simulate engine error
    engines = venue_registry.get("degraded_venue")
    assert engines is not None

    def failing_predict(snapshot):
        raise RuntimeError("Simulated AI Engine prediction crash")

    monkeypatch.setattr(engines.prediction, "predict", failing_predict)

    # Call predictions endpoint -> returns 500 CrowdOSException without leaking internal stack trace
    pred_res = await async_client.get("/api/v1/venues/degraded_venue/predictions")
    assert pred_res.status_code == 500
    data = pred_res.json()
    assert data["status"] == "error"
    assert "Prediction engine error" in data["detail"]
    assert "Simulated AI Engine prediction crash" in data["detail"]

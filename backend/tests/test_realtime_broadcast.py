"""
Sprint 11 — Real-Time Service Integration & Broadcasting Tests.

Verifies end-to-end event broadcasting across EventService, PredictionService,
SessionService, Redis degraded mode, and strict privacy enforcement.
"""
import json
import pytest
from starlette.testclient import TestClient
from app.main import app
from app.realtime.broadcaster import broadcaster
from app.realtime.schemas import (
    WebSocketEnvelope,
    WebSocketEventType,
    OccupancyUpdatePayload,
    PROHIBITED_BIOMETRIC_FIELDS,
)
from app.database.redis.connection import redis_connection


@pytest.fixture
def test_client():
    return TestClient(app)


def test_session_lifecycle_broadcasts(test_client):
    """Verify session transitions (create, start, pause, resume, stop) broadcast real-time updates."""
    venue_id = "rt_venue_session"

    with test_client.websocket_connect(f"/ws/venues/{venue_id}") as ws:
        # Drain initial state
        init_msg = json.loads(ws.receive_text())
        assert init_msg["type"] == "initial_state"

        # 1. Create session via REST
        res_create = test_client.post(f"/api/v1/venues/{venue_id}/sessions", json={"venue_capacity": 500})
        assert res_create.status_code == 201
        session_id = res_create.json()["session_id"]

        create_msg = json.loads(ws.receive_text())
        assert create_msg["type"] == "session_update"
        assert create_msg["data"]["action"] == "create"
        assert create_msg["data"]["session_id"] == session_id

        # 2. Start session
        res_start = test_client.post(f"/api/v1/venues/{venue_id}/sessions/{session_id}/start")
        assert res_start.status_code == 200

        start_msg = json.loads(ws.receive_text())
        assert start_msg["type"] == "session_update"
        assert start_msg["data"]["action"] == "start"

        # 3. Pause session
        res_pause = test_client.post(f"/api/v1/venues/{venue_id}/sessions/{session_id}/pause")
        assert res_pause.status_code == 200

        pause_msg = json.loads(ws.receive_text())
        assert pause_msg["type"] == "session_update"
        assert pause_msg["data"]["action"] == "pause"

        # 4. Resume session
        res_resume = test_client.post(f"/api/v1/venues/{venue_id}/sessions/{session_id}/resume")
        assert res_resume.status_code == 200

        resume_msg = json.loads(ws.receive_text())
        assert resume_msg["type"] == "session_update"
        assert resume_msg["data"]["action"] == "resume"

        # 5. Stop session
        res_stop = test_client.post(f"/api/v1/venues/{venue_id}/sessions/{session_id}/stop")
        assert res_stop.status_code == 200

        stop_msg = json.loads(ws.receive_text())
        assert stop_msg["type"] == "session_update"
        assert stop_msg["data"]["action"] == "stop"


def test_event_ingest_broadcasts_occupancy_and_flow(test_client):
    """Verify event ingestion broadcasts live occupancy and flow updates over WebSocket."""
    venue_id = "rt_venue_events"

    # Setup active session
    res = test_client.post(f"/api/v1/venues/{venue_id}/sessions", json={"venue_capacity": 1000})
    session_id = res.json()["session_id"]
    test_client.post(f"/api/v1/venues/{venue_id}/sessions/{session_id}/start")

    with test_client.websocket_connect(f"/ws/venues/{venue_id}") as ws:
        # Drain initial state
        ws.receive_text()

        # Ingest ENTRY event
        ev_res = test_client.post(
            f"/api/v1/venues/{venue_id}/sessions/{session_id}/events",
            json={"event_type": "ENTRY", "gate_id": "gate_north", "event_id": "ev_rt_1"},
        )
        assert ev_res.status_code == 200

        # Receive occupancy_update
        msg_occ = json.loads(ws.receive_text())
        assert msg_occ["type"] == "occupancy_update"
        assert msg_occ["venue_id"] == venue_id
        assert msg_occ["data"]["total_entries"] >= 1

        # Receive flow_update
        msg_flow = json.loads(ws.receive_text())
        assert msg_flow["type"] == "flow_update"
        assert msg_flow["venue_id"] == venue_id


def test_prediction_triggers_realtime_broadcast(test_client):
    """Verify prediction evaluations broadcast prediction_update over WebSocket."""
    venue_id = "rt_venue_pred"

    # Setup active session
    res = test_client.post(f"/api/v1/venues/{venue_id}/sessions", json={"venue_capacity": 1000})
    session_id = res.json()["session_id"]
    test_client.post(f"/api/v1/venues/{venue_id}/sessions/{session_id}/start")

    with test_client.websocket_connect(f"/ws/venues/{venue_id}") as ws:
        # Drain initial state
        ws.receive_text()

        # Trigger prediction
        pred_res = test_client.get(f"/api/v1/venues/{venue_id}/predictions")
        assert pred_res.status_code == 200

        # Receive prediction_update
        msg_pred = json.loads(ws.receive_text())
        assert msg_pred["type"] == "prediction_update"
        assert msg_pred["venue_id"] == venue_id
        assert "risk_score" in msg_pred["data"]
        assert "primary_recommendation" in msg_pred["data"]


def test_redis_degraded_mode_broadcasting(test_client):
    """Verify broadcaster works seamlessly in local memory mode when Redis is offline."""
    venue_id = "rt_venue_degraded"

    # Simulate Redis offline
    redis_connection.client = None
    redis_connection._is_healthy = False

    with test_client.websocket_connect(f"/ws/venues/{venue_id}") as ws:
        # Drain initial state
        ws.receive_text()

        # Broadcast occupancy update
        import asyncio
        asyncio.run(
            broadcaster.broadcast_occupancy_update(
                venue_id=venue_id,
                session_id="sess_deg_1",
                current_occupancy=45,
                venue_capacity=1000,
                occupancy_ratio=0.045,
                total_entries=50,
                total_exits=5,
                net_flow=45,
            )
        )

        msg = json.loads(ws.receive_text())
        assert msg["type"] == "occupancy_update"
        assert msg["data"]["current_occupancy"] == 45


def test_realtime_privacy_enforcement():
    """Verify WebSocket envelopes strictly reject prohibited biometric vectors."""
    base_data = {"current_occupancy": 10}

    for prohibited in PROHIBITED_BIOMETRIC_FIELDS:
        bad_payload = dict(base_data)
        bad_payload[prohibited] = [0.1, 0.2, 0.3]

        with pytest.raises(ValueError) as exc:
            WebSocketEnvelope(
                type=WebSocketEventType.OCCUPANCY_UPDATE,
                venue_id="priv_venue",
                data=bad_payload,
            )
        assert "PRIVACY VIOLATION" in str(exc.value)

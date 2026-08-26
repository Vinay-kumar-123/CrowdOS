"""
Sprint 11 — Real-Time WebSocket & Event Streaming E2E Verification Script.

Runs comprehensive local E2E checks:
1. WebSocket connection & initial state delivery
2. Multi-client broadcast
3. Venue isolation
4. Broken client fault tolerance
5. Event ingest -> live WebSocket broadcast
6. Prediction evaluation -> live WebSocket broadcast
7. Session lifecycle transitions -> live WebSocket broadcast
8. Redis degraded mode broadcasting
9. Privacy compliance (zero biometric vectors)
"""
import json
import sys
import os
import uuid

# ensure backend on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starlette.testclient import TestClient
from app.main import app
from app.realtime.connection_manager import ws_manager, ConnectionManager
from app.realtime.broadcaster import broadcaster
from app.realtime.schemas import PROHIBITED_BIOMETRIC_FIELDS, WebSocketEnvelope, WebSocketEventType
from app.database.redis.connection import redis_connection

PASS = "PASS"
FAIL = "FAIL"
results = {}


def log(item: str, status: str, detail: str = ""):
    marker = "✓" if status == PASS else "✗"
    print(f"  [{marker}] {item}: {status}" + (f" — {detail}" if detail else ""))
    results[item] = status


def verify_realtime_e2e():
    client = TestClient(app)
    venue_id = f"e2e_ws_venue_{uuid.uuid4().hex[:6]}"

    print("\n═══════════════════════════════════════════════════")
    print("  Sprint 11 — Real-Time WebSocket E2E Verification")
    print("═══════════════════════════════════════════════════")

    # 1. Connection & Initial State
    try:
        with client.websocket_connect(f"/ws/venues/{venue_id}") as ws:
            raw = ws.receive_text()
            data = json.loads(raw)
            assert data["type"] == "initial_state"
            assert data["venue_id"] == venue_id
            assert "timestamp" in data
            log("ws_connect_initial_state", PASS, f"Received initial_state for {venue_id}")
    except Exception as e:
        log("ws_connect_initial_state", FAIL, str(e))

    # 2. Multi-Client Broadcast
    try:
        with client.websocket_connect(f"/ws/venues/{venue_id}") as ws1:
            with client.websocket_connect(f"/ws/venues/{venue_id}") as ws2:
                ws1.receive_text()  # drain initial
                ws2.receive_text()  # drain initial

                import asyncio
                asyncio.run(
                    broadcaster.broadcast_occupancy_update(
                        venue_id=venue_id,
                        session_id="sess_multi",
                        current_occupancy=88,
                        venue_capacity=500,
                        occupancy_ratio=0.176,
                        total_entries=100,
                        total_exits=12,
                        net_flow=88,
                    )
                )

                m1 = json.loads(ws1.receive_text())
                m2 = json.loads(ws2.receive_text())
                assert m1["data"]["current_occupancy"] == 88
                assert m2["data"]["current_occupancy"] == 88
                log("ws_multi_client_broadcast", PASS, "All 2 clients received broadcast")
    except Exception as e:
        log("ws_multi_client_broadcast", FAIL, str(e))

    # 3. Venue Isolation
    try:
        venue_isolated_a = f"iso_a_{uuid.uuid4().hex[:4]}"
        venue_isolated_b = f"iso_b_{uuid.uuid4().hex[:4]}"

        with client.websocket_connect(f"/ws/venues/{venue_isolated_a}") as ws_a:
            with client.websocket_connect(f"/ws/venues/{venue_isolated_b}") as ws_b:
                ws_a.receive_text()
                ws_b.receive_text()

                import asyncio
                asyncio.run(
                    broadcaster.broadcast_flow_update(
                        venue_id=venue_isolated_a,
                        session_id="sess_iso",
                        entry_rate_1m=15.0,
                        entry_rate_5m=12.0,
                        exit_rate_5m=4.0,
                        net_flow_rate_5m=8.0,
                    )
                )

                rec_a = json.loads(ws_a.receive_text())
                assert rec_a["venue_id"] == venue_isolated_a

                # verify ws_b does NOT receive venue_isolated_a message
                ws_b.send_text(json.dumps({"type": "ping"}))
                rec_b = json.loads(ws_b.receive_text())
                assert rec_b["type"] == "pong"
                log("ws_venue_isolation", PASS, f"Messages for {venue_isolated_a} never leaked to {venue_isolated_b}")
    except Exception as e:
        log("ws_venue_isolation", FAIL, str(e))

    # 4. Broken Client Fault Tolerance
    try:
        class BrokenWS:
            async def send_text(self, text):
                raise ConnectionError("Client dead")
            async def close(self):
                pass

        mgr = ConnectionManager()
        broken = BrokenWS()
        mgr._venue_connections["broken_venue"] = {broken}

        import asyncio
        sent = asyncio.run(mgr.broadcast_to_venue("broken_venue", {"msg": "test"}))
        assert sent == 0
        assert broken not in mgr._venue_connections.get("broken_venue", set())
        log("ws_broken_client_tolerance", PASS, "Broken connection safely pruned without crashing broadcast")
    except Exception as e:
        log("ws_broken_client_tolerance", FAIL, str(e))

    # 5. Session Lifecycle End-to-End Broadcast
    try:
        session_venue = f"sess_rt_venue_{uuid.uuid4().hex[:4]}"
        with client.websocket_connect(f"/ws/venues/{session_venue}") as ws:
            ws.receive_text()  # drain initial

            # Create session
            res = client.post(f"/api/v1/venues/{session_venue}/sessions", json={"venue_capacity": 1000})
            sess_id = res.json()["session_id"]
            m_create = json.loads(ws.receive_text())
            assert m_create["type"] == "session_update"
            assert m_create["data"]["action"] == "create"

            # Start session
            client.post(f"/api/v1/venues/{session_venue}/sessions/{sess_id}/start")
            m_start = json.loads(ws.receive_text())
            assert m_start["type"] == "session_update"
            assert m_start["data"]["action"] == "start"

            # Stop session
            client.post(f"/api/v1/venues/{session_venue}/sessions/{sess_id}/stop")
            m_stop = json.loads(ws.receive_text())
            assert m_stop["type"] == "session_update"
            assert m_stop["data"]["action"] == "stop"

            log("ws_session_lifecycle_broadcast", PASS, "create/start/stop transitions broadcasted live")
    except Exception as e:
        log("ws_session_lifecycle_broadcast", FAIL, str(e))

    # 6. Event Ingest End-to-End Broadcast
    try:
        ev_venue = f"ev_rt_venue_{uuid.uuid4().hex[:4]}"
        res = client.post(f"/api/v1/venues/{ev_venue}/sessions", json={"venue_capacity": 1000})
        sess_id = res.json()["session_id"]
        client.post(f"/api/v1/venues/{ev_venue}/sessions/{sess_id}/start")

        with client.websocket_connect(f"/ws/venues/{ev_venue}") as ws:
            ws.receive_text()  # drain initial

            client.post(
                f"/api/v1/venues/{ev_venue}/sessions/{sess_id}/events",
                json={"event_type": "ENTRY", "gate_id": "gate_e2e_rt"},
            )

            m_occ = json.loads(ws.receive_text())
            assert m_occ["type"] == "occupancy_update"
            assert m_occ["data"]["total_entries"] >= 1

            m_flow = json.loads(ws.receive_text())
            assert m_flow["type"] == "flow_update"

            log("ws_event_ingest_broadcast", PASS, "ENTRY event triggered live occupancy & flow updates")
    except Exception as e:
        log("ws_event_ingest_broadcast", FAIL, str(e))

    # 7. Prediction End-to-End Broadcast
    try:
        pred_venue = f"pred_rt_venue_{uuid.uuid4().hex[:4]}"
        res = client.post(f"/api/v1/venues/{pred_venue}/sessions", json={"venue_capacity": 1000})
        sess_id = res.json()["session_id"]
        client.post(f"/api/v1/venues/{pred_venue}/sessions/{sess_id}/start")

        with client.websocket_connect(f"/ws/venues/{pred_venue}") as ws:
            ws.receive_text()  # drain initial

            client.get(f"/api/v1/venues/{pred_venue}/predictions")

            m_pred = json.loads(ws.receive_text())
            assert m_pred["type"] == "prediction_update"
            assert "risk_score" in m_pred["data"]
            assert "primary_recommendation" in m_pred["data"]

            log("ws_prediction_broadcast", PASS, "GET /predictions triggered live prediction_update broadcast")
    except Exception as e:
        log("ws_prediction_broadcast", FAIL, str(e))

    # 8. Redis Degraded Mode
    try:
        deg_venue = f"deg_venue_{uuid.uuid4().hex[:4]}"
        redis_connection.client = None
        redis_connection._is_healthy = False

        with client.websocket_connect(f"/ws/venues/{deg_venue}") as ws:
            ws.receive_text()

            import asyncio
            asyncio.run(
                broadcaster.broadcast_occupancy_update(
                    venue_id=deg_venue,
                    session_id="deg_sess",
                    current_occupancy=25,
                    venue_capacity=1000,
                    occupancy_ratio=0.025,
                    total_entries=30,
                    total_exits=5,
                    net_flow=25,
                )
            )

            m_deg = json.loads(ws.receive_text())
            assert m_deg["data"]["current_occupancy"] == 25
            log("ws_redis_degraded_mode", PASS, "Broadcasting works seamlessly in local memory mode when Redis is down")
    except Exception as e:
        log("ws_redis_degraded_mode", FAIL, str(e))

    # 9. Privacy Enforcement Check
    try:
        for prohibited in PROHIBITED_BIOMETRIC_FIELDS:
            try:
                WebSocketEnvelope(
                    type=WebSocketEventType.OCCUPANCY_UPDATE,
                    venue_id="priv_check",
                    data={prohibited: [0.1, 0.2, 0.3]},
                )
                raise AssertionError(f"Field '{prohibited}' was NOT rejected!")
            except ValueError:
                pass
        log("ws_privacy_enforcement", PASS, f"All {len(PROHIBITED_BIOMETRIC_FIELDS)} prohibited biometric fields rejected")
    except Exception as e:
        log("ws_privacy_enforcement", FAIL, str(e))

    # Summary
    print("\n═══════════════════════════════════════════════════")
    print("  Sprint 11 E2E Verification Summary")
    print("═══════════════════════════════════════════════════")
    passed = sum(1 for s in results.values() if s == PASS)
    total = len(results)
    print(f"  TOTAL: {passed}/{total} PASSED")
    if passed == total:
        print("\n  ✓ Sprint 11 WebSocket Layer: ALL PASS\n")
    else:
        print(f"\n  ✗ Sprint 11 WebSocket Layer: {total - passed} FAILED\n")
        sys.exit(1)


if __name__ == "__main__":
    verify_realtime_e2e()

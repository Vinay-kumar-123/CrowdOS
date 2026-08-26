"""
Sprint 11 — WebSocket Layer Unit & Integration Tests.

Tests:
1. WebSocket connection lifecycle and initial dashboard state delivery.
2. Clean client disconnection.
3. Multi-client support on same venue.
4. Strict venue isolation (events for venue A never reach venue B).
5. Broken client fault tolerance.
6. Client ping/pong heartbeat and malformed message handling.
7. ConnectionManager connection count tracking.
"""
import json
import pytest
from starlette.testclient import TestClient
from app.main import app
from app.realtime.connection_manager import ws_manager, ConnectionManager
from app.realtime.schemas import WebSocketEventType, WebSocketEnvelope, utc_iso_now


@pytest.fixture
def test_client():
    return TestClient(app)


def test_websocket_connect_and_receive_initial_state(test_client):
    """Verify WebSocket client connects to /ws/venues/{venue_id} and receives initial state."""
    venue_id = "ws_test_venue_1"

    with test_client.websocket_connect(f"/ws/venues/{venue_id}") as websocket:
        raw_msg = websocket.receive_text()
        data = json.loads(raw_msg)

        assert data["type"] == WebSocketEventType.INITIAL_STATE.value
        assert data["venue_id"] == venue_id
        assert "timestamp" in data
        assert "data" in data
        assert data["data"]["venue_id"] == venue_id


def test_websocket_disconnect_cleanly(test_client):
    """Verify client disconnection properly unregisters from ConnectionManager."""
    venue_id = "ws_test_venue_2"
    initial_count = ws_manager.get_venue_client_count(venue_id)

    with test_client.websocket_connect(f"/ws/venues/{venue_id}"):
        assert ws_manager.get_venue_client_count(venue_id) == initial_count + 1

    # After exiting context, client is disconnected
    assert ws_manager.get_venue_client_count(venue_id) == initial_count


def test_websocket_multiple_clients_same_venue(test_client):
    """Verify multiple clients connected to the same venue all receive broadcasts."""
    venue_id = "ws_test_venue_multi"

    with test_client.websocket_connect(f"/ws/venues/{venue_id}") as ws1:
        with test_client.websocket_connect(f"/ws/venues/{venue_id}") as ws2:
            # Drain initial state messages
            ws1.receive_text()
            ws2.receive_text()

            # Broadcast custom message
            test_payload = {
                "type": "occupancy_update",
                "venue_id": venue_id,
                "timestamp": utc_iso_now(),
                "data": {"current_occupancy": 150, "total_entries": 200},
            }

            # Import asyncio to call async broadcast
            import asyncio
            asyncio.run(ws_manager.broadcast_to_venue(venue_id, test_payload))

            msg1 = json.loads(ws1.receive_text())
            msg2 = json.loads(ws2.receive_text())

            assert msg1["data"]["current_occupancy"] == 150
            assert msg2["data"]["current_occupancy"] == 150


def test_websocket_venue_isolation(test_client):
    """Verify messages sent to venue A are NEVER delivered to venue B."""
    venue_a = "ws_venue_isolation_a"
    venue_b = "ws_venue_isolation_b"

    with test_client.websocket_connect(f"/ws/venues/{venue_a}") as ws_a:
        with test_client.websocket_connect(f"/ws/venues/{venue_b}") as ws_b:
            # Drain initial states
            ws_a.receive_text()
            ws_b.receive_text()

            # Broadcast only to Venue A
            msg_a = {
                "type": "flow_update",
                "venue_id": venue_a,
                "timestamp": utc_iso_now(),
                "data": {"entry_rate_5m": 42.0},
            }
            import asyncio
            asyncio.run(ws_manager.broadcast_to_venue(venue_a, msg_a))

            # ws_a receives message
            received_a = json.loads(ws_a.receive_text())
            assert received_a["venue_id"] == venue_a
            assert received_a["data"]["entry_rate_5m"] == 42.0

            # ws_b sends a ping to verify its queue has no leaked messages from venue_a
            ws_b.send_text(json.dumps({"type": "ping"}))
            received_b = json.loads(ws_b.receive_text())
            assert received_b["type"] == "pong"


def test_websocket_ping_pong_heartbeat(test_client):
    """Verify ping/pong and heartbeat handling."""
    venue_id = "ws_ping_venue"

    with test_client.websocket_connect(f"/ws/venues/{venue_id}") as ws:
        # Drain initial state
        ws.receive_text()

        # Send JSON ping
        ws.send_text(json.dumps({"type": "ping"}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "pong"
        assert resp["venue_id"] == venue_id

        # Send raw string ping
        ws.send_text("ping")
        resp_raw = json.loads(ws.receive_text())
        assert resp_raw["type"] == "pong"


def test_websocket_malformed_json_handling(test_client):
    """Verify malformed JSON does not crash the WebSocket or drop connection."""
    venue_id = "ws_malformed_venue"

    with test_client.websocket_connect(f"/ws/venues/{venue_id}") as ws:
        # Drain initial state
        ws.receive_text()

        # Send invalid JSON
        ws.send_text("INVALID_JSON_PAYLOAD{{{")
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "error"
        assert "Malformed JSON" in resp["message"]

        # Connection should remain open and functional
        ws.send_text(json.dumps({"type": "ping"}))
        resp2 = json.loads(ws.receive_text())
        assert resp2["type"] == "pong"


@pytest.mark.asyncio
async def test_broken_client_does_not_crash_broadcast():
    """Verify faulty WebSocket connection is safely pruned without breaking broadcast."""
    manager = ConnectionManager()

    class BrokenWebSocket:
        async def send_text(self, text):
            raise ConnectionResetError("Client abruptly disconnected")
        async def close(self):
            pass

    class HealthyWebSocket:
        def __init__(self):
            self.received = []
        async def send_text(self, text):
            self.received.append(text)
        async def close(self):
            pass

    broken = BrokenWebSocket()
    healthy = HealthyWebSocket()

    # Manually add to manager set
    manager._venue_connections["test_broken_venue"] = {broken, healthy}

    # Broadcast
    sent = await manager.broadcast_to_venue("test_broken_venue", {"msg": "hello"})
    assert sent == 1
    assert len(healthy.received) == 1
    # Broken client was pruned
    assert broken not in manager._venue_connections.get("test_broken_venue", set())

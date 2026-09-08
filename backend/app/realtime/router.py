"""
Sprint 11 — Real-Time WebSocket Router.

Provides WebSocket streaming endpoints for dashboard clients with per-venue
routing, initial state delivery, and client heartbeat handling.

Endpoints:
    /ws/venues/{venue_id}  → Venue-specific real-time telemetry stream
    /ws                    → Global telemetry stream (all venues)
"""
import json
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from app.realtime.connection_manager import ws_manager
from app.realtime.schemas import (
    WebSocketEnvelope,
    WebSocketEventType,
    InitialStatePayload,
    utc_iso_now,
)
from app.services.ai_engine_adapter import venue_registry
from app.services.dashboard_service import DashboardService

logger = logging.getLogger("crowdos.realtime.router")

realtime_router = APIRouter(tags=["Real-Time WebSockets"])


def _build_initial_state_envelope(venue_id: str) -> WebSocketEnvelope[InitialStatePayload]:
    """
    Construct initial dashboard state snapshot using existing DashboardService.
    Zero duplicated computation.
    """
    engines = venue_registry.get(venue_id)
    venue_capacity = engines.venue_capacity if engines else 1000
    active_session_id = None
    session_status = None
    dashboard_data = None

    if engines:
        active_sess = engines.intelligence.session_manager.get_active_session()
        if active_sess:
            active_session_id = active_sess.session_id
            session_status = getattr(active_sess, "status", "UNKNOWN")
            if hasattr(session_status, "value"):
                session_status = session_status.value
            else:
                session_status = str(session_status)

            try:
                dashboard_svc = DashboardService(venue_registry)
                snapshot = dashboard_svc.get_dashboard_for_venue_session(venue_id, active_session_id)
                dashboard_data = snapshot.model_dump()
            except Exception as e:
                logger.debug(f"Initial dashboard state generation note: {e}")

    payload = InitialStatePayload(
        venue_id=venue_id,
        venue_capacity=venue_capacity,
        active_session_id=active_session_id,
        session_status=session_status,
        dashboard=dashboard_data,
    )

    return WebSocketEnvelope[InitialStatePayload](
        type=WebSocketEventType.INITIAL_STATE,
        venue_id=venue_id,
        timestamp=utc_iso_now(),
        data=payload,
    )


async def _authenticate_and_authorize_ws(websocket: WebSocket, venue_id: Optional[str] = None) -> bool:
    """
    Authenticate and authorize WebSocket connection BEFORE accepting.
    Extracts token from HttpOnly cookie 'access_token' or query parameter 'token'.
    Enforces that user is active and has access to requested venue_id (or is SUPER_ADMIN).
    Returns True if authorized, False otherwise.
    """
    from app.core.settings import settings
    from app.database.mongodb.connection import db_connection
    from app.repositories.user_repository import UserRepository
    from app.services.auth_service import AuthService
    from app.models.user import UserRole

    # Extract token: cookie first, then query parameter
    token: Optional[str] = websocket.cookies.get("access_token")
    if not token:
        token = websocket.query_params.get("token")

    # In development/test mode, if no users exist in database and no token is provided,
    # allow unauthenticated connection for backward test compatibility
    if not token:
        if settings.ENVIRONMENT.lower() in ("development", "test", "testing"):
            user_col = db_connection.get_collection("users")
            if user_col is None or await user_col.count_documents({}) == 0:
                return True
        return False

    try:
        user_repo = UserRepository(db_connection.get_collection("users"))
        auth_svc = AuthService(user_repo=user_repo)
        user = await auth_svc.verify_token_and_get_user(token)
        if not user or not user.is_active:
            return False

        # If venue_id is provided, enforce venue authorization
        if venue_id is not None:
            clean_vid = venue_id.strip()
            if user.role == UserRole.SUPER_ADMIN:
                return True
            if clean_vid in user.venue_ids or "*" in user.venue_ids:
                return True
            logger.warning(f"WebSocket auth failed: user '{user.email}' not authorized for venue '{clean_vid}'")
            return False

        # Global stream (/ws) is restricted to SUPER_ADMIN
        if user.role == UserRole.SUPER_ADMIN:
            return True
        return False
    except Exception as e:
        logger.debug(f"WebSocket authentication error: {e}")
        return False


@realtime_router.websocket("/ws/venues/{venue_id}")
async def venue_websocket_endpoint(websocket: WebSocket, venue_id: str):
    """
    WebSocket endpoint streaming live operational events for a specific venue.
    Authenticates and authorizes operator before accept().
    Delivers full initial dashboard state immediately upon connection.
    """
    # Validate venue_id format
    if not venue_id or not venue_id.strip():
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    clean_venue_id = venue_id.strip()

    # Pre-accept authentication and venue authorization
    is_authorized = await _authenticate_and_authorize_ws(websocket, clean_venue_id)
    if not is_authorized:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await ws_manager.connect(websocket, clean_venue_id)

    # 1. Send initial state immediately
    try:
        initial_envelope = _build_initial_state_envelope(clean_venue_id)
        await websocket.send_text(initial_envelope.model_dump_json())
    except Exception as e:
        logger.warning(f"Error sending initial state to WebSocket for venue '{clean_venue_id}': {e}")

    # 2. Client communication & heartbeat loop
    try:
        while True:
            text = await websocket.receive_text()
            try:
                # Handle client ping or heartbeat
                data = json.loads(text)
                msg_type = data.get("type", "").lower()
                if msg_type in ("ping", "heartbeat"):
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "venue_id": clean_venue_id,
                        "timestamp": utc_iso_now(),
                    }))
                elif msg_type == "get_state":
                    # Client requested fresh state snapshot
                    fresh_state = _build_initial_state_envelope(clean_venue_id)
                    await websocket.send_text(fresh_state.model_dump_json())
            except json.JSONDecodeError:
                # Safe handling of raw text or malformed JSON
                if text.strip().lower() == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "venue_id": clean_venue_id,
                        "timestamp": utc_iso_now(),
                    }))
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "venue_id": clean_venue_id,
                        "message": "Malformed JSON message received.",
                        "timestamp": utc_iso_now(),
                    }))
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, clean_venue_id)
    except Exception as e:
        logger.warning(f"WebSocket client exception on venue '{clean_venue_id}': {e}")
        await ws_manager.disconnect(websocket, clean_venue_id)


@realtime_router.websocket("/ws")
async def global_websocket_endpoint(websocket: WebSocket):
    """
    Global WebSocket endpoint streaming all real-time events across all venues.
    Restricted to SUPER_ADMIN operators.
    """
    is_authorized = await _authenticate_and_authorize_ws(websocket, venue_id=None)
    if not is_authorized:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await ws_manager.connect(websocket, None)
    try:
        while True:
            text = await websocket.receive_text()
            if text.strip().lower() == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "venue_id": "all",
                    "timestamp": utc_iso_now(),
                }))
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, None)
    except Exception as e:
        logger.warning(f"Global WebSocket client exception: {e}")
        await ws_manager.disconnect(websocket, None)

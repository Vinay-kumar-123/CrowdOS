"""
Session Endpoints — Sprint 10.

REST API for monitoring session lifecycle management with MongoDB persistence.
Sprint 7's SessionManager manages the in-flight state machine, while SessionRepository
persists lifecycle history and session summaries.

Routes:
    POST   /v1/venues/{venue_id}/sessions                      → create session
    GET    /v1/venues/{venue_id}/sessions                      → list sessions
    GET    /v1/venues/{venue_id}/sessions/active               → get active session
    GET    /v1/venues/{venue_id}/sessions/{session_id}         → get session by ID
    POST   /v1/venues/{venue_id}/sessions/{session_id}/start   → start (CREATED/PAUSED -> ACTIVE)
    POST   /v1/venues/{venue_id}/sessions/{session_id}/pause   → pause (ACTIVE -> PAUSED)
    POST   /v1/venues/{venue_id}/sessions/{session_id}/resume  → resume (PAUSED -> ACTIVE)
    POST   /v1/venues/{venue_id}/sessions/{session_id}/stop    → stop (ACTIVE/PAUSED -> STOPPED)
    POST   /v1/venues/{venue_id}/sessions/check-expirations    → check & expire sessions
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional, Dict, Any
from app.services.ai_engine_adapter import venue_registry
from app.services.session_service import SessionService
from app.repositories.session_repository import SessionRepository
from app.repositories.venue_repository import VenueRepository
from app.dependencies.database import get_session_repository, get_venue_repository
from app.schemas.session import (
    SessionCreateRequest,
    SessionStatusResponse,
    SessionListResponse,
    SessionActionResponse,
    SessionSummaryResponse,
)

router = APIRouter(prefix="/v1/venues/{venue_id}/sessions", tags=["Sessions"])


def _get_session_service(
    session_repo: SessionRepository = Depends(get_session_repository),
    venue_repo: VenueRepository = Depends(get_venue_repository),
) -> SessionService:
    return SessionService(
        venue_registry,
        session_repo=session_repo,
        venue_repo=venue_repo,
    )


@router.post(
    "",
    response_model=SessionStatusResponse,
    status_code=201,
    summary="Create monitoring session",
    description="Creates a new continuous monitoring session for a venue in CREATED state and persists it to MongoDB.",
)
async def create_session(
    venue_id: str,
    body: SessionCreateRequest,
    svc: SessionService = Depends(_get_session_service),
):
    return await svc.create_session(venue_id=venue_id, request=body)


@router.get(
    "",
    response_model=SessionListResponse,
    summary="List all sessions",
    description="Returns all sessions created for the specified venue from in-memory engine and MongoDB.",
)
async def list_sessions(
    venue_id: str,
    svc: SessionService = Depends(_get_session_service),
):
    return await svc.list_sessions(venue_id=venue_id)


@router.get(
    "/active",
    response_model=Optional[SessionStatusResponse],
    summary="Get active session",
    description="Returns the currently ACTIVE monitoring session for the venue, or null if no session is active.",
)
async def get_active_session(
    venue_id: str,
    svc: SessionService = Depends(_get_session_service),
):
    return await svc.get_active_session(venue_id=venue_id)


@router.post(
    "/check-expirations",
    response_model=Dict[str, Any],
    summary="Trigger session expiration check",
    description="Evaluates active/paused sessions against max_duration_seconds using Sprint 7 SessionManager and syncs expired sessions to MongoDB.",
)
async def check_expirations(
    venue_id: str,
    now_epoch: Optional[float] = Query(default=None, description="Optional epoch timestamp to evaluate expiration against"),
    svc: SessionService = Depends(_get_session_service),
):
    expired = await svc.check_expirations(venue_id=venue_id, now_epoch=now_epoch)
    return {
        "venue_id": venue_id,
        "expired_count": len(expired),
        "expired_session_ids": expired,
    }


@router.get(
    "/{session_id}",
    response_model=SessionStatusResponse,
    summary="Get session details",
    description="Returns details and current state for a specific session ID.",
)
async def get_session(
    venue_id: str,
    session_id: str,
    svc: SessionService = Depends(_get_session_service),
):
    return await svc.get_session(venue_id=venue_id, session_id=session_id)


@router.post(
    "/{session_id}/start",
    response_model=SessionActionResponse,
    summary="Start monitoring session",
    description="Transitions session from CREATED or PAUSED state to ACTIVE state. Rejects invalid transitions with HTTP 409.",
)
async def start_session(
    venue_id: str,
    session_id: str,
    svc: SessionService = Depends(_get_session_service),
):
    return await svc.start_session(venue_id=venue_id, session_id=session_id)


@router.post(
    "/{session_id}/pause",
    response_model=SessionActionResponse,
    summary="Pause monitoring session",
    description="Transitions session from ACTIVE to PAUSED state. Rejects invalid transitions with HTTP 409.",
)
async def pause_session(
    venue_id: str,
    session_id: str,
    svc: SessionService = Depends(_get_session_service),
):
    return await svc.pause_session(venue_id=venue_id, session_id=session_id)


@router.post(
    "/{session_id}/resume",
    response_model=SessionActionResponse,
    summary="Resume monitoring session",
    description="Transitions session from PAUSED state back to ACTIVE state.",
)
async def resume_session(
    venue_id: str,
    session_id: str,
    svc: SessionService = Depends(_get_session_service),
):
    return await svc.resume_session(venue_id=venue_id, session_id=session_id)


@router.post(
    "/{session_id}/stop",
    response_model=SessionSummaryResponse,
    summary="Stop monitoring session",
    description="Transitions session to terminal STOPPED state and returns an immutable SessionSummary snapshot generated by Sprint 7.",
)
async def stop_session(
    venue_id: str,
    session_id: str,
    svc: SessionService = Depends(_get_session_service),
):
    return await svc.stop_session(venue_id=venue_id, session_id=session_id)

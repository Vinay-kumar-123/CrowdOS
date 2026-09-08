"""
Dashboard Endpoints — Sprint 9.

REST API exposing the unified real-time dashboard snapshot for monitoring sessions.

Routes:
    GET /v1/sessions/{session_id}/dashboard
    GET /v1/venues/{venue_id}/sessions/{session_id}/dashboard
"""
from fastapi import APIRouter, Depends
from app.services.ai_engine_adapter import venue_registry
from app.services.dashboard_service import DashboardService
from app.schemas.dashboard import DashboardSnapshotResponse

from app.models.user import UserDBModel, UserRole
from app.dependencies.auth import require_venue_access, get_current_active_user

router = APIRouter(tags=["Dashboard"])


def _get_dashboard_service() -> DashboardService:
    return DashboardService(venue_registry)


@router.get(
    "/v1/sessions/{session_id}/dashboard",
    response_model=DashboardSnapshotResponse,
    summary="Get session dashboard snapshot",
    description="Returns an aggregated live dashboard snapshot containing session status, occupancy, flow, density, alerts, anomalies, risk scoring, trend detection, short-horizon forecasts, recommendations, and gate summaries.",
)
async def get_session_dashboard(
    session_id: str,
    svc: DashboardService = Depends(_get_dashboard_service),
    user: UserDBModel = Depends(get_current_active_user),
):
    """
    Unified dashboard endpoint queried by session_id across registered venues.
    Enforces venue-scoped authorization on the matching session's venue.
    """
    match = svc._registry.find_venue_by_session(session_id)
    if match is not None:
        matched_venue_id, _ = match
        if user.role != UserRole.SUPER_ADMIN and "*" not in user.venue_ids:
            if matched_venue_id not in user.venue_ids:
                from app.core.exceptions import AuthorizationException
                raise AuthorizationException(f"Access to venue '{matched_venue_id}' for session '{session_id}' is forbidden.")
    return svc.get_dashboard_by_session_id(session_id)


@router.get(
    "/v1/venues/{venue_id}/sessions/{session_id}/dashboard",
    response_model=DashboardSnapshotResponse,
    summary="Get venue session dashboard snapshot",
    description="Returns an aggregated live dashboard snapshot for a specific venue and session.",
)
async def get_venue_session_dashboard(
    venue_id: str,
    session_id: str,
    svc: DashboardService = Depends(_get_dashboard_service),
    user: UserDBModel = Depends(require_venue_access),
):
    """
    Unified dashboard endpoint scoped by venue_id and session_id.
    """
    return svc.get_dashboard_for_venue_session(venue_id=venue_id, session_id=session_id)

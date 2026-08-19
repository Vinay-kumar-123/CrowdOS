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
):
    """
    Unified dashboard endpoint queried by session_id across registered venues.
    """
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
):
    """
    Unified dashboard endpoint scoped by venue_id and session_id.
    """
    return svc.get_dashboard_for_venue_session(venue_id=venue_id, session_id=session_id)

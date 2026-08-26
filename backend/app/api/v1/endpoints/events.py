"""
Event Ingest Endpoints — Sprint 10.

REST API for pushing movement events (ENTRY/EXIT) into Sprint 7's
EventIntelligenceEngine and persisting operational events & alerts into MongoDB.

Routes:
    POST /v1/venues/{venue_id}/sessions/{session_id}/events → ingest event
"""
from fastapi import APIRouter, Depends
from app.services.ai_engine_adapter import venue_registry
from app.services.event_service import EventService
from app.repositories.event_repository import EventRepository
from app.repositories.alert_repository import AlertRepository
from app.dependencies.database import get_event_repository, get_alert_repository
from app.schemas.events import EventIngestRequest, EventIngestResponse

router = APIRouter(prefix="/v1/venues/{venue_id}/sessions/{session_id}", tags=["Events"])


def _get_event_service(
    event_repo: EventRepository = Depends(get_event_repository),
    alert_repo: AlertRepository = Depends(get_alert_repository),
) -> EventService:
    return EventService(
        venue_registry,
        event_repo=event_repo,
        alert_repo=alert_repo,
    )


@router.post(
    "/events",
    response_model=EventIngestResponse,
    status_code=200,
    summary="Ingest movement event",
    description="Ingests a single movement event (ENTRY or EXIT). Updates OccupancyTracker, routes event into Sprint 7 Intelligence Engine, and persists operational records to MongoDB.",
)
async def ingest_event(
    venue_id: str,
    session_id: str,
    body: EventIngestRequest,
    svc: EventService = Depends(_get_event_service),
):
    return await svc.ingest_event(venue_id=venue_id, session_id=session_id, request=body)

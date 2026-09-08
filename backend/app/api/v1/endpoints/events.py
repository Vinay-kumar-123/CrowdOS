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
from app.services.visitor_history_service import VisitorHistoryService
from app.repositories.event_repository import EventRepository
from app.repositories.alert_repository import AlertRepository
from app.repositories.visitor_repository import (
    VisitorRepository,
    VisitorEventRepository,
    VisitRepository,
)
from app.dependencies.database import (
    get_event_repository,
    get_alert_repository,
    get_visitor_repository,
    get_visitor_event_repository,
    get_visit_repository,
)
from app.schemas.events import EventIngestRequest, EventIngestResponse

router = APIRouter(prefix="/v1/venues/{venue_id}/sessions/{session_id}", tags=["Events"])


def _get_visitor_history_service(
    visitor_repo: VisitorRepository = Depends(get_visitor_repository),
    event_repo: VisitorEventRepository = Depends(get_visitor_event_repository),
    visit_repo: VisitRepository = Depends(get_visit_repository),
) -> VisitorHistoryService:
    return VisitorHistoryService(
        visitor_repo=visitor_repo,
        event_repo=event_repo,
        visit_repo=visit_repo,
    )


def _get_event_service(
    event_repo: EventRepository = Depends(get_event_repository),
    alert_repo: AlertRepository = Depends(get_alert_repository),
    visitor_history_svc: VisitorHistoryService = Depends(_get_visitor_history_service),
) -> EventService:
    return EventService(
        venue_registry,
        event_repo=event_repo,
        alert_repo=alert_repo,
        visitor_history_svc=visitor_history_svc,
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

"""
Event Ingest Endpoints — Sprint 9.

REST API for pushing movement events (ENTRY/EXIT) into Sprint 7's
EventIntelligenceEngine.

Routes:
    POST /v1/venues/{venue_id}/sessions/{session_id}/events → ingest event
"""
from fastapi import APIRouter, Depends
from app.services.ai_engine_adapter import venue_registry
from app.services.event_service import EventService
from app.schemas.events import EventIngestRequest, EventIngestResponse

router = APIRouter(prefix="/v1/venues/{venue_id}/sessions/{session_id}", tags=["Events"])


def _get_event_service() -> EventService:
    return EventService(venue_registry)


@router.post(
    "/events",
    response_model=EventIngestResponse,
    status_code=200,
    summary="Ingest movement event",
    description="Ingests a single movement event (ENTRY or EXIT). Instantiates authoritative Sprint 6 Event schemas, updates OccupancyTracker, and routes the event into Sprint 7 Intelligence Engine for flow analysis, anomaly detection, and alert processing.",
)
async def ingest_event(
    venue_id: str,
    session_id: str,
    body: EventIngestRequest,
    svc: EventService = Depends(_get_event_service),
):
    return svc.ingest_event(venue_id=venue_id, session_id=session_id, request=body)

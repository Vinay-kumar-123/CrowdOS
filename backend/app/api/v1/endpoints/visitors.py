"""
Visitor History Endpoints — Sprint 13.

REST API for querying historical visitor movement intelligence:
- GET /v1/venues/{venue_id}/visitors/{visitor_id}           -> Visitor summary profile
- GET /v1/venues/{venue_id}/visitors/{visitor_id}/events    -> Movement event timeline
- GET /v1/venues/{venue_id}/visitors/{visitor_id}/visits    -> Visits list with presence durations
- GET /v1/venues/{venue_id}/visitors/{visitor_id}/history   -> Consolidated history

All queries strictly enforce venue isolation.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from app.services.visitor_history_service import VisitorHistoryService
from app.repositories.visitor_repository import (
    VisitorRepository,
    VisitorEventRepository,
    VisitRepository,
)
from app.dependencies.database import (
    get_visitor_repository,
    get_visitor_event_repository,
    get_visit_repository,
)
from app.schemas.visitors import (
    VisitorResponse,
    VisitorEventsListResponse,
    VisitsListResponse,
    VisitorHistoryResponse,
)

router = APIRouter(prefix="/v1/venues/{venue_id}/visitors", tags=["Visitors"])


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


@router.get(
    "/{visitor_id}",
    response_model=VisitorResponse,
    status_code=200,
    summary="Get visitor profile summary",
    description="Retrieves the persistent visitor profile for a venue, including first/last seen and entry/exit/visit totals.",
)
async def get_visitor_profile(
    venue_id: str,
    visitor_id: str,
    svc: VisitorHistoryService = Depends(_get_visitor_history_service),
):
    return await svc.get_visitor_profile(venue_id=venue_id, visitor_id=visitor_id)


@router.get(
    "/{visitor_id}/events",
    response_model=VisitorEventsListResponse,
    status_code=200,
    summary="Get visitor movement timeline",
    description="Returns a paginated chronological timeline of physical ENTRY and EXIT events for a visitor in a venue.",
)
async def get_visitor_events(
    venue_id: str,
    visitor_id: str,
    start_time: Optional[str] = Query(default=None, description="Start date/time filter (ISO 8601 or YYYY-MM-DD)"),
    end_time: Optional[str] = Query(default=None, description="End date/time filter (ISO 8601 or YYYY-MM-DD)"),
    event_type: Optional[str] = Query(default=None, description="Filter by 'ENTRY' or 'EXIT'"),
    limit: int = Query(default=50, ge=1, le=200, description="Page limit"),
    skip: int = Query(default=0, ge=0, description="Items to skip"),
    svc: VisitorHistoryService = Depends(_get_visitor_history_service),
):
    return await svc.get_visitor_events(
        venue_id=venue_id,
        visitor_id=visitor_id,
        start_time=start_time,
        end_time=end_time,
        event_type=event_type,
        limit=limit,
        skip=skip,
    )


@router.get(
    "/{visitor_id}/visits",
    response_model=VisitsListResponse,
    status_code=200,
    summary="Get visitor visits",
    description="Returns a paginated list of physical presence visits (bounded by ENTRY and matching EXIT) for a visitor in a venue.",
)
async def get_visitor_visits(
    venue_id: str,
    visitor_id: str,
    start_time: Optional[str] = Query(default=None, description="Start date/time filter (ISO 8601 or YYYY-MM-DD)"),
    end_time: Optional[str] = Query(default=None, description="End date/time filter (ISO 8601 or YYYY-MM-DD)"),
    status: Optional[str] = Query(default=None, description="Filter by visit status: 'OPEN' or 'COMPLETED'"),
    limit: int = Query(default=50, ge=1, le=200, description="Page limit"),
    skip: int = Query(default=0, ge=0, description="Items to skip"),
    svc: VisitorHistoryService = Depends(_get_visitor_history_service),
):
    return await svc.get_visitor_visits(
        venue_id=venue_id,
        visitor_id=visitor_id,
        start_time=start_time,
        end_time=end_time,
        status=status,
        limit=limit,
        skip=skip,
    )


@router.get(
    "/{visitor_id}/history",
    response_model=VisitorHistoryResponse,
    status_code=200,
    summary="Get consolidated visitor history",
    description="Returns consolidated visitor profile summary, recent visits, and recent movement events.",
)
async def get_visitor_history(
    venue_id: str,
    visitor_id: str,
    start_time: Optional[str] = Query(default=None, description="Start date/time filter (ISO 8601 or YYYY-MM-DD)"),
    end_time: Optional[str] = Query(default=None, description="End date/time filter (ISO 8601 or YYYY-MM-DD)"),
    limit: int = Query(default=50, ge=1, le=200, description="Limit for visits and events"),
    svc: VisitorHistoryService = Depends(_get_visitor_history_service),
):
    return await svc.get_visitor_history(
        venue_id=venue_id,
        visitor_id=visitor_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )

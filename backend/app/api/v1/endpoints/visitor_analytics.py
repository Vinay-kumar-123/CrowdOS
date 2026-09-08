"""
Visitor Analytics Endpoints — Sprint 14.

REST API for querying historical visitor and venue movement intelligence:
Visitor-Level Endpoints:
- GET /api/v1/venues/{venue_id}/visitors/{visitor_id}/analytics/summary
- GET /api/v1/venues/{venue_id}/visitors/{visitor_id}/analytics/daily
- GET /api/v1/venues/{venue_id}/visitors/{visitor_id}/analytics/gates
- GET /api/v1/venues/{venue_id}/visitors/{visitor_id}/analytics/duration
- GET /api/v1/venues/{venue_id}/visitors/{visitor_id}/analytics/timeline
- GET /api/v1/venues/{venue_id}/visitors/{visitor_id}/analytics/frequency

Venue-Level Endpoints:
- GET /api/v1/venues/{venue_id}/analytics/visitors
- GET /api/v1/venues/{venue_id}/analytics/daily
- GET /api/v1/venues/{venue_id}/analytics/summary
- GET /api/v1/venues/{venue_id}/analytics/gates
- GET /api/v1/venues/{venue_id}/analytics/duration

All queries strictly enforce venue isolation.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from app.services.visitor_analytics_service import VisitorAnalyticsService
from app.repositories.visitor_analytics_repository import VisitorAnalyticsRepository
from app.dependencies.database import get_visitor_analytics_repository
from app.schemas.visitor_analytics import (
    VisitorAnalyticsSummaryResponse,
    VisitorDailyAnalyticsListResponse,
    VisitorGateAnalyticsResponse,
    VisitorDurationAnalyticsResponse,
    VisitorTimelineResponse,
    VisitorFrequencyResponse,
    VenueVisitorAnalyticsResponse,
    VenueDailyTrendsResponse,
    VenueAnalyticsSummaryResponse,
)

from app.dependencies.auth import require_venue_access

router = APIRouter(
    prefix="/v1",
    tags=["Visitor Analytics"],
    dependencies=[Depends(require_venue_access)],
)


def _get_visitor_analytics_service(
    analytics_repo: VisitorAnalyticsRepository = Depends(get_visitor_analytics_repository),
) -> VisitorAnalyticsService:
    return VisitorAnalyticsService(analytics_repo=analytics_repo)


# ============================================================================
# Visitor-Level Analytics
# ============================================================================

@router.get(
    "/venues/{venue_id}/visitors/{visitor_id}/analytics/summary",
    response_model=VisitorAnalyticsSummaryResponse,
    status_code=200,
    summary="Get visitor profile analytics summary",
    description="Retrieves consolidated analytics for a visitor in a venue including entry/exit totals, total/completed/open visits, and duration metrics.",
)
async def get_visitor_analytics_summary(
    venue_id: str,
    visitor_id: str,
    svc: VisitorAnalyticsService = Depends(_get_visitor_analytics_service),
):
    return await svc.get_visitor_summary(venue_id=venue_id, visitor_id=visitor_id)


@router.get(
    "/venues/{venue_id}/visitors/{visitor_id}/analytics/daily",
    response_model=VisitorDailyAnalyticsListResponse,
    status_code=200,
    summary="Get daily visitor analytics",
    description="Returns day-by-day movement metrics and visit presence for a visitor over an optional date range.",
)
async def get_visitor_daily_analytics(
    venue_id: str,
    visitor_id: str,
    start_time: Optional[str] = Query(default=None, description="Start date/time (ISO 8601 or YYYY-MM-DD)"),
    end_time: Optional[str] = Query(default=None, description="End date/time (ISO 8601 or YYYY-MM-DD)"),
    svc: VisitorAnalyticsService = Depends(_get_visitor_analytics_service),
):
    return await svc.get_visitor_daily_analytics(
        venue_id=venue_id, visitor_id=visitor_id, start_time=start_time, end_time=end_time
    )


@router.get(
    "/venues/{venue_id}/visitors/{visitor_id}/analytics/gates",
    response_model=VisitorGateAnalyticsResponse,
    status_code=200,
    summary="Get visitor gate usage analytics",
    description="Returns gate usage statistics, percentages, and top entry/exit gates for a visitor.",
)
async def get_visitor_gate_analytics(
    venue_id: str,
    visitor_id: str,
    start_time: Optional[str] = Query(default=None, description="Start date/time (ISO 8601 or YYYY-MM-DD)"),
    end_time: Optional[str] = Query(default=None, description="End date/time (ISO 8601 or YYYY-MM-DD)"),
    svc: VisitorAnalyticsService = Depends(_get_visitor_analytics_service),
):
    return await svc.get_visitor_gate_analytics(
        venue_id=venue_id, visitor_id=visitor_id, start_time=start_time, end_time=end_time
    )


@router.get(
    "/venues/{venue_id}/visitors/{visitor_id}/analytics/duration",
    response_model=VisitorDurationAnalyticsResponse,
    status_code=200,
    summary="Get visitor duration analytics",
    description="Returns average, minimum, maximum, median, and total duration for completed visits.",
)
async def get_visitor_duration_analytics(
    venue_id: str,
    visitor_id: str,
    start_time: Optional[str] = Query(default=None, description="Start date/time (ISO 8601 or YYYY-MM-DD)"),
    end_time: Optional[str] = Query(default=None, description="End date/time (ISO 8601 or YYYY-MM-DD)"),
    svc: VisitorAnalyticsService = Depends(_get_visitor_analytics_service),
):
    return await svc.get_visitor_duration_analytics(
        venue_id=venue_id, visitor_id=visitor_id, start_time=start_time, end_time=end_time
    )


@router.get(
    "/venues/{venue_id}/visitors/{visitor_id}/analytics/timeline",
    response_model=VisitorTimelineResponse,
    status_code=200,
    summary="Get visitor daily timeline",
    description="Returns a chronological daily movement timeline preserving distinct multiple visits per day.",
)
async def get_visitor_timeline(
    venue_id: str,
    visitor_id: str,
    start_time: Optional[str] = Query(default=None, description="Start date/time (ISO 8601 or YYYY-MM-DD)"),
    end_time: Optional[str] = Query(default=None, description="End date/time (ISO 8601 or YYYY-MM-DD)"),
    svc: VisitorAnalyticsService = Depends(_get_visitor_analytics_service),
):
    return await svc.get_visitor_timeline(
        venue_id=venue_id, visitor_id=visitor_id, start_time=start_time, end_time=end_time
    )


@router.get(
    "/venues/{venue_id}/visitors/{visitor_id}/analytics/frequency",
    response_model=VisitorFrequencyResponse,
    status_code=200,
    summary="Get visitor frequency and return patterns",
    description="Calculates visit frequency, average visits per active day, and returning visitor classification.",
)
async def get_visitor_frequency(
    venue_id: str,
    visitor_id: str,
    svc: VisitorAnalyticsService = Depends(_get_visitor_analytics_service),
):
    return await svc.get_visitor_frequency(venue_id=venue_id, visitor_id=visitor_id)


# ============================================================================
# Venue-Level Analytics
# ============================================================================

@router.get(
    "/venues/{venue_id}/analytics/visitors",
    response_model=VenueVisitorAnalyticsResponse,
    status_code=200,
    summary="Get venue-level visitor analytics",
    description="Calculates venue-wide unique visitors, new vs returning visitors, entry/exit totals, visit counts, and visit durations over a date range.",
)
async def get_venue_visitor_analytics(
    venue_id: str,
    start_time: Optional[str] = Query(default=None, description="Start date/time (ISO 8601 or YYYY-MM-DD)"),
    end_time: Optional[str] = Query(default=None, description="End date/time (ISO 8601 or YYYY-MM-DD)"),
    svc: VisitorAnalyticsService = Depends(_get_visitor_analytics_service),
):
    return await svc.get_venue_visitor_analytics(
        venue_id=venue_id, start_time=start_time, end_time=end_time
    )


@router.get(
    "/venues/{venue_id}/analytics/daily",
    response_model=VenueDailyTrendsResponse,
    status_code=200,
    summary="Get venue-level daily visitor trends",
    description="Returns chronological daily visitor metrics and duration trends across the venue.",
)
async def get_venue_daily_trends(
    venue_id: str,
    start_time: Optional[str] = Query(default=None, description="Start date/time (ISO 8601 or YYYY-MM-DD)"),
    end_time: Optional[str] = Query(default=None, description="End date/time (ISO 8601 or YYYY-MM-DD)"),
    svc: VisitorAnalyticsService = Depends(_get_visitor_analytics_service),
):
    return await svc.get_venue_daily_trends(
        venue_id=venue_id, start_time=start_time, end_time=end_time
    )


@router.get(
    "/venues/{venue_id}/analytics/summary",
    response_model=VenueAnalyticsSummaryResponse,
    status_code=200,
    summary="Get consolidated venue analytics summary",
    description="Returns consolidated venue-level analytics overview, gate analytics, duration metrics, and daily trends.",
)
async def get_venue_analytics_summary(
    venue_id: str,
    start_time: Optional[str] = Query(default=None, description="Start date/time (ISO 8601 or YYYY-MM-DD)"),
    end_time: Optional[str] = Query(default=None, description="End date/time (ISO 8601 or YYYY-MM-DD)"),
    svc: VisitorAnalyticsService = Depends(_get_visitor_analytics_service),
):
    return await svc.get_venue_analytics_summary(
        venue_id=venue_id, start_time=start_time, end_time=end_time
    )


@router.get(
    "/venues/{venue_id}/analytics/gates",
    response_model=VisitorGateAnalyticsResponse,
    status_code=200,
    summary="Get venue-wide gate usage analytics",
    description="Returns gate usage statistics, percentages, and top entry/exit gates across the entire venue.",
)
async def get_venue_gate_analytics(
    venue_id: str,
    start_time: Optional[str] = Query(default=None, description="Start date/time (ISO 8601 or YYYY-MM-DD)"),
    end_time: Optional[str] = Query(default=None, description="End date/time (ISO 8601 or YYYY-MM-DD)"),
    svc: VisitorAnalyticsService = Depends(_get_visitor_analytics_service),
):
    return await svc.get_visitor_gate_analytics(
        venue_id=venue_id, visitor_id=None, start_time=start_time, end_time=end_time
    )


@router.get(
    "/venues/{venue_id}/analytics/duration",
    response_model=VisitorDurationAnalyticsResponse,
    status_code=200,
    summary="Get venue-wide duration analytics",
    description="Returns average, minimum, maximum, median, and total duration for completed visits across the entire venue.",
)
async def get_venue_duration_analytics(
    venue_id: str,
    start_time: Optional[str] = Query(default=None, description="Start date/time (ISO 8601 or YYYY-MM-DD)"),
    end_time: Optional[str] = Query(default=None, description="End date/time (ISO 8601 or YYYY-MM-DD)"),
    svc: VisitorAnalyticsService = Depends(_get_visitor_analytics_service),
):
    return await svc.get_visitor_duration_analytics(
        venue_id=venue_id, visitor_id=None, start_time=start_time, end_time=end_time
    )

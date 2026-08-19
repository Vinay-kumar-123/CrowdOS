"""
Intelligence Endpoints — Sprint 9.

REST API exposing Sprint 7 intelligence analytics for a venue.
All data comes from EventIntelligenceEngine — NO duplicate calculations.

Routes:
    GET /v1/venues/{venue_id}/intelligence              → current full snapshot
    GET /v1/venues/{venue_id}/intelligence/flow         → venue-level flow metrics
    GET /v1/venues/{venue_id}/intelligence/flow/gates   → all gate flow metrics
    GET /v1/venues/{venue_id}/intelligence/flow/gates/{gate_id}  → single gate flow
    GET /v1/venues/{venue_id}/intelligence/occupancy    → occupancy summary
    GET /v1/venues/{venue_id}/intelligence/density      → density + congestion state
    GET /v1/venues/{venue_id}/intelligence/dwell        → dwell time metrics
"""
from fastapi import APIRouter, Depends
from typing import Dict
from app.services.ai_engine_adapter import venue_registry
from app.services.intelligence_service import IntelligenceService
from app.schemas.intelligence import (
    CurrentIntelligenceResponse,
    FlowMetricsResponse,
    OccupancySummaryResponse,
    DensityStateResponse,
    DwellMetricsResponse,
)

router = APIRouter(prefix="/v1/venues/{venue_id}/intelligence", tags=["Intelligence"])


def _get_intelligence_service() -> IntelligenceService:
    return IntelligenceService(venue_registry)


@router.get(
    "",
    response_model=CurrentIntelligenceResponse,
    summary="Get current intelligence snapshot",
    description="Returns aggregated real-time crowd metrics including flow rates, current occupancy, density classification, dwell time stats, and active alerts from Sprint 7.",
)
async def get_current_intelligence(
    venue_id: str,
    svc: IntelligenceService = Depends(_get_intelligence_service),
):
    return svc.get_current_intelligence(venue_id=venue_id)


@router.get(
    "/flow",
    response_model=FlowMetricsResponse,
    summary="Get venue-level flow metrics",
    description="Returns venue-wide flow analytics across 1m, 5m, 15m, and 60m sliding windows with cumulative entries/exits/net flow.",
)
async def get_venue_flow(
    venue_id: str,
    svc: IntelligenceService = Depends(_get_intelligence_service),
):
    return svc.get_venue_flow(venue_id=venue_id)


@router.get(
    "/flow/gates",
    response_model=Dict[str, FlowMetricsResponse],
    summary="Get all gate flow metrics",
    description="Returns flow analytics for every active gate in the venue.",
)
async def get_all_gate_flows(
    venue_id: str,
    svc: IntelligenceService = Depends(_get_intelligence_service),
):
    return svc.get_all_gate_flows(venue_id=venue_id)


@router.get(
    "/flow/gates/{gate_id}",
    response_model=FlowMetricsResponse,
    summary="Get single gate flow metrics",
    description="Returns flow analytics for the specified gate_id.",
)
async def get_gate_flow(
    venue_id: str,
    gate_id: str,
    svc: IntelligenceService = Depends(_get_intelligence_service),
):
    return svc.get_gate_flow(venue_id=venue_id, gate_id=gate_id)


@router.get(
    "/occupancy",
    response_model=OccupancySummaryResponse,
    summary="Get venue occupancy summary",
    description="Returns authoritative physical occupancy summary from Sprint 6 OccupancyState including per-gate breakdown and busiest/least active gates.",
)
async def get_occupancy_summary(
    venue_id: str,
    svc: IntelligenceService = Depends(_get_intelligence_service),
):
    return svc.get_occupancy_summary(venue_id=venue_id)


@router.get(
    "/density",
    response_model=DensityStateResponse,
    summary="Get crowd density and congestion state",
    description="Returns current crowd density level (LOW, MODERATE, HIGH, CRITICAL) and congestion level (NORMAL, BUILDING, CONGESTED, SEVERE_CONGESTION) with hysteresis.",
)
async def get_density_state(
    venue_id: str,
    svc: IntelligenceService = Depends(_get_intelligence_service),
):
    state = svc.get_current_intelligence(venue_id=venue_id)
    return state.density


@router.get(
    "/dwell",
    response_model=DwellMetricsResponse,
    summary="Get venue dwell time metrics",
    description="Returns average, median, and p95 dwell time metrics derived from completed visitor journeys.",
)
async def get_dwell_metrics(
    venue_id: str,
    svc: IntelligenceService = Depends(_get_intelligence_service),
):
    state = svc.get_current_intelligence(venue_id=venue_id)
    return state.dwell

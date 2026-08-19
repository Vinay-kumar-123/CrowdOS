"""
Prediction Endpoints — Sprint 9.

REST API exposing Sprint 8 predictive risk intelligence.
Triggers PredictionEngine.predict() with a live PredictionInputSnapshot
built from current Sprint 7 engine state.

Routes:
    GET /v1/venues/{venue_id}/predictions              → run one prediction cycle
    GET /v1/venues/{venue_id}/predictions/metrics      → Sprint 8 engine metrics
    GET /v1/venues/{venue_id}/predictions/risk         → current risk level only
    GET /v1/venues/{venue_id}/predictions/decision     → current decision only
    GET /v1/venues/{venue_id}/predictions/forecast/occupancy → occupancy forecast
    GET /v1/venues/{venue_id}/predictions/forecast/flow      → flow forecast
"""
from fastapi import APIRouter, Depends
from app.services.ai_engine_adapter import venue_registry
from app.services.prediction_service import PredictionService
from app.schemas.prediction import (
    PredictionResultResponse,
    RiskResultResponse,
    DecisionResultResponse,
    OccupancyForecastResponse,
    FlowForecastResponse,
)
from typing import Dict, Optional

router = APIRouter(prefix="/v1/venues/{venue_id}/predictions", tags=["Predictions"])


def _get_prediction_service() -> PredictionService:
    return PredictionService(venue_registry)


@router.get(
    "",
    response_model=PredictionResultResponse,
    summary="Evaluate full prediction cycle",
    description="Runs a complete Sprint 8 prediction cycle for the active session. Computes predictive crowd risk, trend classification, operational decision actions, short-horizon forecasts, and per-gate predictions.",
)
async def get_prediction(
    venue_id: str,
    svc: PredictionService = Depends(_get_prediction_service),
):
    return svc.get_prediction(venue_id=venue_id)


@router.get(
    "/metrics",
    response_model=Dict,
    summary="Get prediction engine metrics",
    description="Returns internal performance and prediction evaluation metrics from Sprint 8 PredictionMetricsTracker.",
)
async def get_prediction_metrics(
    venue_id: str,
    svc: PredictionService = Depends(_get_prediction_service),
):
    return svc.get_prediction_metrics(venue_id=venue_id)


@router.get(
    "/risk",
    response_model=Optional[RiskResultResponse],
    summary="Get current predictive risk level",
    description="Returns explainable multi-factor predictive risk score and level (LOW, GUARDED, ELEVATED, HIGH, CRITICAL) for the venue.",
)
async def get_current_risk(
    venue_id: str,
    svc: PredictionService = Depends(_get_prediction_service),
):
    result = svc.get_prediction(venue_id=venue_id)
    return result.venue_risk


@router.get(
    "/decision",
    response_model=Optional[DecisionResultResponse],
    summary="Get operational decision recommendations",
    description="Returns prioritized actionable crowd management recommendations (e.g. MONITOR, REDIRECT_FLOW, CONTROL_ENTRY, ESCALATE_OPERATOR).",
)
async def get_current_decision(
    venue_id: str,
    svc: PredictionService = Depends(_get_prediction_service),
):
    result = svc.get_prediction(venue_id=venue_id)
    return result.venue_decision


@router.get(
    "/forecast/occupancy",
    response_model=Optional[OccupancyForecastResponse],
    summary="Get short-horizon occupancy forecast",
    description="Returns linear extrapolated occupancy forecasts across 5m, 10m, and 15m horizons with capacity exceedance risk probabilities.",
)
async def get_occupancy_forecast(
    venue_id: str,
    svc: PredictionService = Depends(_get_prediction_service),
):
    result = svc.get_prediction(venue_id=venue_id)
    return result.occupancy_forecast


@router.get(
    "/forecast/flow",
    response_model=Optional[FlowForecastResponse],
    summary="Get short-horizon flow rate forecast",
    description="Returns projected entry rate and net flow trends over future horizons.",
)
async def get_flow_forecast(
    venue_id: str,
    svc: PredictionService = Depends(_get_prediction_service),
):
    result = svc.get_prediction(venue_id=venue_id)
    return result.flow_forecast

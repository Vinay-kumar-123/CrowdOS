"""
Prediction Service — Sprint 9.

Triggers Sprint 8 PredictionEngine.predict() using a live snapshot built
from Sprint 7 engine state via the SnapshotBuilder.

Architecture:
    1. Gets active session from Sprint 7 SessionManager
    2. Builds PredictionInputSnapshot from Sprint 7 state
    3. Calls Sprint 8 PredictionEngine.predict(snapshot)
    4. Maps PredictionResult → Sprint 9 Pydantic response schemas

NO business logic is duplicated here. Risk scoring, trend detection,
forecasting, and decision logic all live in Sprint 8 ai-engine/prediction/.
"""
import logging
from typing import Optional
from app.services.ai_engine_adapter import VenueEngineRegistry, VenueEngines
from app.services.snapshot_builder import build_snapshot
from app.schemas.prediction import (
    PredictionResultResponse,
    RiskResultResponse,
    RiskFactorResponse,
    TrendResultResponse,
    DecisionResultResponse,
    OccupancyForecastResponse,
    OccupancyForecastHorizonResponse,
    FlowForecastResponse,
    GatePredictionResponse,
)
from app.core.exceptions import NotFoundException, CrowdOSException

logger = logging.getLogger("crowdos.prediction_service")


class PredictionService:
    """
    Service layer for Sprint 8 prediction queries.
    One call per venue per request cycle.
    """

    def __init__(self, registry: VenueEngineRegistry):
        self._registry = registry

    def _get_engines(self, venue_id: str) -> VenueEngines:
        engines = self._registry.get(venue_id)
        if engines is None:
            raise NotFoundException(f"Venue '{venue_id}' not initialized.")
        return engines

    def get_prediction(self, venue_id: str) -> PredictionResultResponse:
        """
        Run one prediction cycle for the venue's active session.
        Returns mapped PredictionResultResponse.
        """
        engines = self._get_engines(venue_id)

        # Determine active session id and status
        active_session = engines.intelligence.session_manager.get_active_session()
        if active_session is None:
            raise CrowdOSException(
                detail=f"No active session for venue '{venue_id}'. Start a session first.",
                status_code=400,
            )

        session_id = active_session.session_id
        session_status = _status_str(active_session)

        # Build snapshot from Sprint 7 engine state
        snapshot = build_snapshot(engines, session_id=session_id, session_status=session_status)

        if snapshot is None:
            # AI Engine not available — return stub response
            return PredictionResultResponse(
                session_id=session_id,
                venue_id=venue_id,
                timestamp="",
                status="unavailable",
                message="AI Engine not available — running in stub mode.",
            )

        # Delegate to Sprint 8 PredictionEngine
        try:
            result = engines.prediction.predict(snapshot)
        except Exception as e:
            logger.error(f"PredictionEngine.predict() failed for venue {venue_id}: {e}")
            raise CrowdOSException(
                detail=f"Prediction engine error: {str(e)}",
                status_code=500,
            )

        return _map_prediction_result(result)

    def get_prediction_metrics(self, venue_id: str) -> dict:
        """Returns Sprint 8 internal metrics for the venue."""
        engines = self._get_engines(venue_id)
        return engines.prediction.get_metrics()


# ---------------------------------------------------------------------------
# Mapping helpers — PredictionResult → Response schemas
# ---------------------------------------------------------------------------

def _status_str(session) -> str:
    st = getattr(session, "status", None)
    if st is None:
        return "UNKNOWN"
    if hasattr(st, "value"):
        return st.value
    return str(st)


def _map_prediction_result(result) -> PredictionResultResponse:
    """Map Sprint 8 PredictionResult object to Sprint 9 response schema."""
    # Use to_dict() for safe field extraction
    d = result.to_dict() if hasattr(result, "to_dict") else {}

    venue_risk = _map_risk(d.get("venue_risk")) if d.get("venue_risk") else None
    venue_trend = _map_trend(d.get("venue_trend")) if d.get("venue_trend") else None
    venue_decision = _map_decision(d.get("venue_decision")) if d.get("venue_decision") else None
    occ_forecast = _map_occ_forecast(d.get("occupancy_forecast")) if d.get("occupancy_forecast") else None
    flow_forecast = _map_flow_forecast(d.get("flow_forecast")) if d.get("flow_forecast") else None

    # Gate results
    gate_results = {}
    for gate_id, gate_data in (d.get("gate_results") or {}).items():
        if isinstance(gate_data, dict) and "error" not in gate_data:
            gate_results[gate_id] = GatePredictionResponse(
                gate_id=gate_id,
                risk=_map_risk(gate_data.get("risk", {})),
                trend=_map_trend(gate_data.get("trend", {})),
                decision=_map_decision(gate_data.get("decision", {})),
            )

    return PredictionResultResponse(
        session_id=d.get("session_id", ""),
        venue_id=d.get("venue_id", ""),
        timestamp=d.get("timestamp", ""),
        status=d.get("status", "ok"),
        message=d.get("message", ""),
        venue_risk=venue_risk,
        venue_trend=venue_trend,
        venue_decision=venue_decision,
        occupancy_forecast=occ_forecast,
        flow_forecast=flow_forecast,
        gate_results=gate_results,
        processing_time_ms=d.get("processing_time_ms", 0.0),
    )


def _map_risk(d: Optional[dict]) -> RiskResultResponse:
    if not d:
        return RiskResultResponse()
    factors = []
    for f in d.get("factors", []):
        if isinstance(f, dict):
            factors.append(RiskFactorResponse(
                name=f.get("name", ""),
                raw_value=f.get("raw_value", 0.0),
                normalized_value=f.get("normalized_value", 0.0),
                contribution=f.get("contribution", 0.0),
                feature_unavailable=f.get("feature_unavailable", False),
            ))
    return RiskResultResponse(
        risk_level=d.get("risk_level", "LOW"),
        score=d.get("score", 0.0),
        data_sufficient=d.get("data_sufficient", True),
        factors=factors,
    )


def _map_trend(d: Optional[dict]) -> TrendResultResponse:
    if not d:
        return TrendResultResponse()
    return TrendResultResponse(
        direction=d.get("direction", "STABLE"),
        slope=d.get("slope"),
        confidence=d.get("confidence", "LOW"),
        n_observations=d.get("n_observations", 0),
    )


def _map_decision(d: Optional[dict]) -> DecisionResultResponse:
    if not d:
        return DecisionResultResponse()
    return DecisionResultResponse(
        action=d.get("action", "MONITOR"),
        reason=d.get("reason", ""),
        priority=d.get("priority", 0),
        gate_id=d.get("gate_id"),
        secondary_reasons=d.get("secondary_reasons", []),
    )


def _map_occ_forecast(d: Optional[dict]) -> Optional[OccupancyForecastResponse]:
    if not d:
        return None
    horizons = []
    for h in d.get("forecasts", []):
        if isinstance(h, dict):
            horizons.append(OccupancyForecastHorizonResponse(
                horizon_minutes=h.get("horizon_minutes", 0),
                projected_value=h.get("projected_value"),
                capacity_exceedance_probability=h.get("capacity_exceedance_probability", 0.0),
                will_exceed_capacity=h.get("will_exceed_capacity", False),
                confidence=h.get("confidence", "INSUFFICIENT_DATA"),
            ))
    return OccupancyForecastResponse(
        venue_id=d.get("venue_id", ""),
        session_id=d.get("session_id", ""),
        timestamp=d.get("timestamp", ""),
        n_observations=d.get("n_observations", 0),
        forecasts=horizons,
    )


def _map_flow_forecast(d: Optional[dict]) -> Optional[FlowForecastResponse]:
    if not d:
        return None
    return FlowForecastResponse(
        venue_id=d.get("venue_id", ""),
        session_id=d.get("session_id", ""),
        timestamp=d.get("timestamp", ""),
        n_observations=d.get("n_observations", 0),
        projected_entry_rate=d.get("projected_entry_rate"),
        projected_net_flow=d.get("projected_net_flow"),
        confidence=d.get("confidence", "INSUFFICIENT_DATA"),
    )

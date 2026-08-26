"""
Prediction Service — Sprint 10.

Triggers Sprint 8 PredictionEngine.predict() using a live snapshot built
from Sprint 7 engine state and persists evaluated risk snapshots to MongoDB.

Architecture:
    1. Gets active session from Sprint 7 SessionManager
    2. Builds PredictionInputSnapshot from Sprint 7 state
    3. Calls Sprint 8 PredictionEngine.predict(snapshot)
    4. Maps PredictionResult → Sprint 9 Pydantic response schemas
    5. Persists prediction snapshot to MongoDB (PredictionRepository)

NO AI algorithm logic is duplicated here. Risk scoring, trend detection,
forecasting, and decision logic live entirely in Sprint 8 ai-engine/prediction/.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from app.services.ai_engine_adapter import VenueEngineRegistry, VenueEngines
from app.services.snapshot_builder import build_snapshot
from app.repositories.prediction_repository import PredictionRepository
from app.models.prediction import PredictionDBModel
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
    Service layer for Sprint 8 prediction queries with MongoDB persistence.
    """

    def __init__(
        self,
        registry: VenueEngineRegistry,
        prediction_repo: Optional[PredictionRepository] = None,
    ):
        self._registry = registry
        self._prediction_repo = prediction_repo

    def _get_engines(self, venue_id: str) -> VenueEngines:
        engines = self._registry.get(venue_id)
        if engines is None:
            raise NotFoundException(f"Venue '{venue_id}' not initialized.")
        return engines

    async def get_prediction(self, venue_id: str) -> PredictionResultResponse:
        """
        Run one prediction cycle for the venue's active session.
        Persists outcome to MongoDB and returns mapped PredictionResultResponse.
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

        response = _map_prediction_result(result)

        # Persist prediction snapshot to MongoDB
        if self._prediction_repo and self._prediction_repo.is_available and response.status == "ok":
            try:
                risk_data = response.venue_risk
                trend_data = response.venue_trend
                decision_data = response.venue_decision
                factors_dump = [f.model_dump() for f in risk_data.factors] if risk_data else []

                pred_model = PredictionDBModel(
                    prediction_id=str(uuid.uuid4()),
                    session_id=session_id,
                    venue_id=venue_id,
                    timestamp=response.timestamp or datetime.now(timezone.utc).isoformat(),
                    risk_score=risk_data.score if risk_data else 0.0,
                    risk_level=risk_data.risk_level if risk_data else "LOW",
                    factors=factors_dump,
                    trend_direction=trend_data.direction if trend_data else "STABLE",
                    trend_slope=trend_data.slope if trend_data else None,
                    trend_confidence=trend_data.confidence if trend_data else "LOW",
                    occupancy_forecast=response.occupancy_forecast.model_dump() if response.occupancy_forecast else None,
                    flow_forecast=response.flow_forecast.model_dump() if response.flow_forecast else None,
                    primary_recommendation=decision_data.action if decision_data else "MONITOR",
                    recommendations=[decision_data.action] if decision_data else ["MONITOR"],
                    processing_time_ms=response.processing_time_ms,
                )
                await self._prediction_repo.save_prediction(pred_model)
            except Exception as pe:
                logger.error(f"Failed to persist prediction to MongoDB: {pe}")

        # Real-time prediction broadcasting (Sprint 11)
        try:
            from app.realtime.broadcaster import broadcaster
            risk_data = response.venue_risk
            trend_data = response.venue_trend
            decision_data = response.venue_decision
            await broadcaster.broadcast_prediction_update(
                venue_id=venue_id,
                session_id=session_id,
                prediction_id=str(uuid.uuid4()),
                risk_score=risk_data.score if risk_data else 0.0,
                risk_level=risk_data.risk_level if risk_data else "LOW",
                trend_direction=trend_data.direction if trend_data else "STABLE",
                trend_slope=trend_data.slope if trend_data else None,
                trend_confidence=trend_data.confidence if trend_data else "LOW",
                primary_recommendation=decision_data.action if decision_data else "MONITOR",
                recommendations=[decision_data.action] if decision_data else ["MONITOR"],
                factors=[f.model_dump() for f in risk_data.factors] if (risk_data and risk_data.factors) else [],
                occupancy_forecast=response.occupancy_forecast.model_dump() if response.occupancy_forecast else None,
                flow_forecast=response.flow_forecast.model_dump() if response.flow_forecast else None,
                processing_time_ms=response.processing_time_ms,
            )
        except Exception as be:
            logger.warning(f"Real-time prediction broadcast non-fatal notice: {be}")

        return response

    async def list_prediction_history(
        self,
        venue_id: str,
        session_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Fetch historical prediction snapshots from MongoDB."""
        if not self._prediction_repo or not self._prediction_repo.is_available:
            return []

        docs = await self._prediction_repo.list_predictions(
            venue_id=venue_id,
            session_id=session_id,
            limit=limit,
        )
        return [doc.model_dump() for doc in docs]

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

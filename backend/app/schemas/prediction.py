"""
Prediction Schemas — Sprint 9.

Response Pydantic models for Sprint 8 prediction query endpoints.
Allowlist-based — only safe, operational predictive intelligence fields.
NO biometric fields, NO raw signals, NO internal engine state.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------

class RiskFactorResponse(BaseModel):
    """A single risk contributing factor."""
    name: str
    raw_value: float = 0.0
    normalized_value: float = 0.0
    contribution: float = 0.0
    feature_unavailable: bool = False


class RiskResultResponse(BaseModel):
    """Venue or gate-level risk assessment response."""
    risk_level: str = "LOW"
    score: float = 0.0
    data_sufficient: bool = True
    factors: List[RiskFactorResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Trend
# ---------------------------------------------------------------------------

class TrendResultResponse(BaseModel):
    """Risk trend direction result."""
    direction: str = "STABLE"
    slope: Optional[float] = None
    confidence: str = "LOW"
    n_observations: int = 0


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

class OccupancyForecastHorizonResponse(BaseModel):
    """Single occupancy forecast horizon."""
    horizon_minutes: int
    projected_value: Optional[float] = None
    capacity_exceedance_probability: float = 0.0
    will_exceed_capacity: bool = False
    confidence: str = "INSUFFICIENT_DATA"


class OccupancyForecastResponse(BaseModel):
    """Occupancy forecast result."""
    venue_id: str
    session_id: str
    timestamp: str
    n_observations: int = 0
    forecasts: List[OccupancyForecastHorizonResponse] = Field(default_factory=list)


class FlowForecastResponse(BaseModel):
    """Flow forecast result."""
    venue_id: str
    session_id: str
    timestamp: str
    n_observations: int = 0
    projected_entry_rate: Optional[float] = None
    projected_net_flow: Optional[float] = None
    confidence: str = "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

class DecisionResultResponse(BaseModel):
    """Operational decision recommendation."""
    action: str = "MONITOR"
    reason: str = ""
    priority: int = 0
    gate_id: Optional[str] = None
    secondary_reasons: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Gate prediction
# ---------------------------------------------------------------------------

class GatePredictionResponse(BaseModel):
    """Prediction result for a single gate."""
    gate_id: str
    risk: RiskResultResponse
    trend: TrendResultResponse
    decision: DecisionResultResponse


# ---------------------------------------------------------------------------
# Full prediction result
# ---------------------------------------------------------------------------

class PredictionResultResponse(BaseModel):
    """
    Full Sprint 8 prediction result for a venue.
    Allowlist-safe: only operational intelligence. NO raw engine internals.
    """
    session_id: str
    venue_id: str
    timestamp: str
    status: str = "ok"
    message: str = ""
    venue_risk: Optional[RiskResultResponse] = None
    venue_trend: Optional[TrendResultResponse] = None
    venue_decision: Optional[DecisionResultResponse] = None
    occupancy_forecast: Optional[OccupancyForecastResponse] = None
    flow_forecast: Optional[FlowForecastResponse] = None
    gate_results: Dict[str, GatePredictionResponse] = Field(default_factory=dict)
    processing_time_ms: float = 0.0

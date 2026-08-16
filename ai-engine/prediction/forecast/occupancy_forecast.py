"""
OccupancyForecaster — Short-horizon occupancy projection using linear extrapolation.

Method: Theil-Sen slope extrapolation over recent bounded window observations.
  projected = current_occupancy + slope * horizon_minutes

Physical bounds enforcement:
  projected < 0       → clip to 0.0; status = NEGATIVE_CLIPPED
  projected > capacity → DO NOT clip; status = CAPACITY_EXCEEDED_RISK
    (The signal that capacity WILL be exceeded is the valuable intelligence.
     Silently clipping it would destroy the warning.)

Confidence (data-sufficiency-based ONLY — no statistical percentages):
  INSUFFICIENT_DATA: n < 5 observations
  LOW:    n in [5, 9]  OR  time_span < 120s
  MEDIUM: n in [10, 19] AND time_span >= 120s
  HIGH:   n >= 20 AND time_span >= 300s

If confidence == INSUFFICIENT_DATA: projected_value = None, slope = None.
NEVER fabricate a projection from insufficient data.
"""
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field
from prediction.trend.trend_detector import _theil_sen_slope
from prediction.utils.bounded_history import BoundedObservationHistory
from prediction.config.settings import PredictionSettings, default_prediction_settings


class ForecastConfidence(str, Enum):
    """
    Data-sufficiency-based confidence only.
    These are NOT statistical confidence intervals.
    They describe how much historical data is available.
    """
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # n < 5
    LOW = "LOW"                               # n in [5,9] or span < 120s
    MEDIUM = "MEDIUM"                         # n in [10,19], span >= 120s
    HIGH = "HIGH"                             # n >= 20, span >= 300s


class ForecastStatus(str, Enum):
    OK = "OK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    CAPACITY_EXCEEDED_RISK = "CAPACITY_EXCEEDED_RISK"
    NEGATIVE_CLIPPED = "NEGATIVE_CLIPPED"


def _compute_confidence(n: int, time_span: float) -> ForecastConfidence:
    """Data-sufficiency-based confidence classification."""
    if n < 5:
        return ForecastConfidence.INSUFFICIENT_DATA
    if n >= 20 and time_span >= 300.0:
        return ForecastConfidence.HIGH
    if n >= 10 and time_span >= 120.0:
        return ForecastConfidence.MEDIUM
    return ForecastConfidence.LOW


class OccupancyForecastPoint(BaseModel):
    horizon_minutes: int
    current_value: float
    projected_value: Optional[float] = None
    slope: Optional[float] = Field(default=None, description="Theil-Sen slope persons/minute")
    confidence: ForecastConfidence = ForecastConfidence.INSUFFICIENT_DATA
    status: ForecastStatus = ForecastStatus.INSUFFICIENT_DATA
    method: str = "theil_sen_linear_extrapolation"
    n_observations: int = 0
    time_span_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class OccupancyForecastResult(BaseModel):
    session_id: str
    venue_id: str
    timestamp: str
    venue_capacity: int
    forecasts: List[OccupancyForecastPoint] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "venue_id": self.venue_id,
            "timestamp": self.timestamp,
            "venue_capacity": self.venue_capacity,
            "forecasts": [f.to_dict() for f in self.forecasts],
        }


class OccupancyForecaster:
    """Forecasts venue occupancy over configurable horizons using Theil-Sen extrapolation."""

    def __init__(self, settings: Optional[PredictionSettings] = None):
        self.settings = settings or default_prediction_settings
        self._history = BoundedObservationHistory(
            max_observations=self.settings.max_history_observations,
            max_age_seconds=self.settings.max_history_age_seconds,
        )

    def add_observation(self, occupancy: float, timestamp_epoch: float) -> None:
        self._history.add(timestamp_epoch, occupancy)

    def forecast(
        self,
        session_id: str,
        venue_id: str,
        timestamp: str,
        current_occupancy: float,
        venue_capacity: int,
    ) -> OccupancyForecastResult:
        # Use recent observations for short-horizon trend slope (up to 30 observations)
        observations = self._history.get_recent(30)

        # Deduplicate (keep last per epoch) and sort
        deduped: dict = {}
        for epoch_ts, val in observations:
            deduped[epoch_ts] = val
        points: List[Tuple[float, float]] = sorted(deduped.items())
        n_pts = len(points)
        time_span = (points[-1][0] - points[0][0]) if n_pts >= 2 else 0.0
        confidence = _compute_confidence(n_pts, time_span)
        slope = _theil_sen_slope(points) if n_pts >= 2 else None

        forecasts = []
        for h_min in self.settings.forecast_horizons_minutes:
            if confidence == ForecastConfidence.INSUFFICIENT_DATA or slope is None:
                forecasts.append(OccupancyForecastPoint(
                    horizon_minutes=h_min,
                    current_value=current_occupancy,
                    projected_value=None,
                    slope=None,
                    confidence=ForecastConfidence.INSUFFICIENT_DATA,
                    status=ForecastStatus.INSUFFICIENT_DATA,
                    n_observations=n_pts,
                    time_span_seconds=round(time_span, 1),
                ))
                continue

            projected = current_occupancy + slope * h_min
            status = ForecastStatus.OK

            if venue_capacity > 0 and projected > venue_capacity:
                status = ForecastStatus.CAPACITY_EXCEEDED_RISK
                # DO NOT clip — preserve the over-capacity signal
            elif projected < 0.0:
                projected = 0.0
                status = ForecastStatus.NEGATIVE_CLIPPED

            forecasts.append(OccupancyForecastPoint(
                horizon_minutes=h_min,
                current_value=current_occupancy,
                projected_value=round(projected, 1),
                slope=round(slope, 4),
                confidence=confidence,
                status=status,
                n_observations=n_pts,
                time_span_seconds=round(time_span, 1),
            ))

        return OccupancyForecastResult(
            session_id=session_id,
            venue_id=venue_id,
            timestamp=timestamp,
            venue_capacity=venue_capacity,
            forecasts=forecasts,
        )

    def reset(self) -> None:
        self._history.reset()

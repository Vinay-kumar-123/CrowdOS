"""
FlowForecaster — Short-horizon entry/net-flow rate projection.

Uses Theil-Sen linear extrapolation over recent bounded window observations.
Same ForecastConfidence model as OccupancyForecaster.

Net flow projection: min_clip=None (net flow can be negative — do not clip)
Entry rate projection: min_clip=0.0 (rates cannot be physically negative)
"""
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field
from prediction.trend.trend_detector import _theil_sen_slope
from prediction.forecast.occupancy_forecast import (
    ForecastConfidence, ForecastStatus, _compute_confidence
)
from prediction.utils.bounded_history import BoundedObservationHistory
from prediction.config.settings import PredictionSettings, default_prediction_settings


class FlowForecastPoint(BaseModel):
    horizon_minutes: int
    metric: str
    current_value: float
    projected_value: Optional[float] = None
    slope: Optional[float] = None
    confidence: ForecastConfidence = ForecastConfidence.INSUFFICIENT_DATA
    status: ForecastStatus = ForecastStatus.INSUFFICIENT_DATA
    method: str = "theil_sen_linear_extrapolation"
    n_observations: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class FlowForecastResult(BaseModel):
    session_id: str
    venue_id: str
    timestamp: str
    entry_rate_forecasts: List[FlowForecastPoint] = Field(default_factory=list)
    net_flow_forecasts: List[FlowForecastPoint] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


def _project_rate(
    history: BoundedObservationHistory,
    current: float,
    horizons: List[int],
    metric: str,
    min_clip: Optional[float],
) -> List[FlowForecastPoint]:
    observations = history.get_recent(30)
    deduped: dict = {}
    for t, v in observations:
        deduped[t] = v
    points: List[Tuple[float, float]] = sorted(deduped.items())
    n_pts = len(points)
    time_span = (points[-1][0] - points[0][0]) if n_pts >= 2 else 0.0
    confidence = _compute_confidence(n_pts, time_span)
    slope = _theil_sen_slope(points) if n_pts >= 2 else None

    results = []
    for h_min in horizons:
        if confidence == ForecastConfidence.INSUFFICIENT_DATA or slope is None:
            results.append(FlowForecastPoint(
                horizon_minutes=h_min,
                metric=metric,
                current_value=current,
                confidence=ForecastConfidence.INSUFFICIENT_DATA,
                status=ForecastStatus.INSUFFICIENT_DATA,
                n_observations=n_pts,
            ))
            continue
        projected = current + slope * h_min
        status = ForecastStatus.OK
        if min_clip is not None and projected < min_clip:
            projected = min_clip
            status = ForecastStatus.NEGATIVE_CLIPPED
        results.append(FlowForecastPoint(
            horizon_minutes=h_min,
            metric=metric,
            current_value=current,
            projected_value=round(projected, 3),
            slope=round(slope, 4),
            confidence=confidence,
            status=status,
            n_observations=n_pts,
        ))
    return results


class FlowForecaster:
    """Projects entry rate and net flow rate over configurable horizons."""

    def __init__(self, settings: Optional[PredictionSettings] = None):
        self.settings = settings or default_prediction_settings
        self._entry_history = BoundedObservationHistory(
            max_observations=self.settings.max_history_observations,
            max_age_seconds=self.settings.max_history_age_seconds,
        )
        self._net_flow_history = BoundedObservationHistory(
            max_observations=self.settings.max_history_observations,
            max_age_seconds=self.settings.max_history_age_seconds,
        )

    def add_observation(
        self,
        entry_rate: float,
        net_flow_rate: float,
        timestamp_epoch: float,
    ) -> None:
        self._entry_history.add(timestamp_epoch, entry_rate)
        self._net_flow_history.add(timestamp_epoch, net_flow_rate)  # signed preserved

    def forecast(
        self,
        session_id: str,
        venue_id: str,
        timestamp: str,
        current_entry_rate: float,
        current_net_flow: float,
    ) -> FlowForecastResult:
        entry_pts = _project_rate(
            self._entry_history, current_entry_rate,
            self.settings.forecast_horizons_minutes, "entry_rate_5m",
            min_clip=0.0,  # entry rate physically cannot be negative
        )
        net_pts = _project_rate(
            self._net_flow_history, current_net_flow,
            self.settings.forecast_horizons_minutes, "net_flow_rate_5m",
            min_clip=None,  # net flow CAN be negative — preserve signal
        )
        return FlowForecastResult(
            session_id=session_id,
            venue_id=venue_id,
            timestamp=timestamp,
            entry_rate_forecasts=entry_pts,
            net_flow_forecasts=net_pts,
        )

    def reset(self) -> None:
        self._entry_history.reset()
        self._net_flow_history.reset()

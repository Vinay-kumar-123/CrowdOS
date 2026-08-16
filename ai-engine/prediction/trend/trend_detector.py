"""
TrendDetector — Slope-based risk trend detection using Theil-Sen median slope.

Algorithm: Theil-Sen median slope over last N observations.
  - Robust to outliers (median of pairwise slopes)
  - slope units: risk score points per minute

Handles:
  - missing observations     → INSUFFICIENT_DATA
  - irregular timestamps     → uses actual time differences (seconds)
  - duplicate timestamps     → deduplicated by keeping last value per epoch
  - out-of-order timestamps  → sorted before slope computation
  - insufficient history     → INSUFFICIENT_DATA with explicit message
  - constant history         → slope = 0.0, STABLE/WEAK

Thread-safe: TrendDetector uses BoundedObservationHistory which is thread-safe.
The caller provides timestamps — no background scheduler.
"""
from typing import List, Optional, Tuple
from prediction.trend.trend_state import TrendDirection, TrendStrength, TrendResult
from prediction.config.thresholds import TrendThresholds, default_thresholds
from prediction.config.settings import PredictionSettings, default_prediction_settings
from prediction.utils.bounded_history import BoundedObservationHistory


def _theil_sen_slope(points: List[Tuple[float, float]]) -> Optional[float]:
    """
    Compute Theil-Sen median slope from (time_epoch_seconds, value) pairs.
    Returns slope in value-units per MINUTE.
    Returns None if fewer than 2 points.
    Returns 0.0 if all timestamps are identical (constant-time observations).
    """
    if len(points) < 2:
        return None
    slopes = []
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            dt_seconds = points[j][0] - points[i][0]
            if abs(dt_seconds) < 1e-6:
                continue  # near-duplicate timestamp — skip this pair
            dy = points[j][1] - points[i][1]
            slopes.append(dy / (dt_seconds / 60.0))  # per minute
    if not slopes:
        return 0.0  # all timestamps identical → no slope computable → treat as 0
    slopes.sort()
    n = len(slopes)
    if n % 2 == 1:
        return slopes[n // 2]
    return (slopes[n // 2 - 1] + slopes[n // 2]) / 2.0


class TrendDetector:
    """
    Thread-safe trend detector using Theil-Sen slope over bounded history.
    One instance per venue (or per gate for gate-level trend).
    """

    def __init__(
        self,
        settings: Optional[PredictionSettings] = None,
        thresholds: Optional[TrendThresholds] = None,
    ):
        self.settings = settings or default_prediction_settings
        self.thresholds = thresholds or default_thresholds.trend
        self._history = BoundedObservationHistory(
            max_observations=self.settings.max_history_observations,
            max_age_seconds=self.settings.max_history_age_seconds,
        )

    def add_observation(self, score: float, timestamp_epoch: float) -> None:
        """Record a risk score observation with its epoch timestamp."""
        self._history.add(timestamp_epoch, score)

    def detect(self, session_id: str, venue_id: str, timestamp: str) -> TrendResult:
        """Detect trend from current bounded history."""
        observations = self._history.get_recent(self.settings.trend_window_observations)
        n_raw = len(observations)

        if n_raw < self.settings.min_trend_observations:
            return TrendResult(
                session_id=session_id,
                venue_id=venue_id,
                timestamp=timestamp,
                direction=TrendDirection.INSUFFICIENT_DATA,
                strength=TrendStrength.UNKNOWN,
                slope=None,
                n_observations=n_raw,
                time_span_seconds=0.0,
                message=(
                    f"Insufficient data: {n_raw} observations "
                    f"(minimum required: {self.settings.min_trend_observations})"
                ),
            )

        # Deduplicate by keeping last value per epoch timestamp
        deduped: dict = {}
        for epoch_ts, score in observations:
            deduped[epoch_ts] = score
        points = sorted(deduped.items())  # sorted by time

        time_span = (points[-1][0] - points[0][0]) if len(points) >= 2 else 0.0
        slope = _theil_sen_slope(points)

        if slope is None:
            return TrendResult(
                session_id=session_id,
                venue_id=venue_id,
                timestamp=timestamp,
                direction=TrendDirection.INSUFFICIENT_DATA,
                strength=TrendStrength.UNKNOWN,
                slope=None,
                n_observations=len(points),
                time_span_seconds=time_span,
                message="All deduplicated observations have identical timestamps",
            )

        # Classify direction
        t = self.thresholds
        if slope >= t.increasing_slope_threshold:
            direction = TrendDirection.INCREASING
        elif slope <= t.decreasing_slope_threshold:
            direction = TrendDirection.DECREASING
        else:
            direction = TrendDirection.STABLE

        # Classify strength
        abs_slope = abs(slope)
        if direction == TrendDirection.STABLE:
            strength = TrendStrength.WEAK
        elif abs_slope >= t.strong_strength_threshold:
            strength = TrendStrength.STRONG
        elif abs_slope >= t.weak_strength_threshold:
            strength = TrendStrength.MODERATE
        else:
            strength = TrendStrength.WEAK

        return TrendResult(
            session_id=session_id,
            venue_id=venue_id,
            timestamp=timestamp,
            direction=direction,
            strength=strength,
            slope=round(slope, 4),
            n_observations=len(points),
            time_span_seconds=round(time_span, 1),
            message=(
                f"Trend: {direction.value} ({strength.value}) | "
                f"slope={slope:.3f} pts/min | n={len(points)} | "
                f"span={time_span:.0f}s"
            ),
        )

    def reset(self) -> None:
        """Clear all observation history."""
        self._history.reset()

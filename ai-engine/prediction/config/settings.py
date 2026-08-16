"""
Global Settings for CrowdOS Sprint 8 Prediction Engine.
"""
from typing import List
from pydantic import BaseModel, Field


class PredictionSettings(BaseModel):
    """Configuration for the Prediction Engine."""

    # Bounded history
    max_history_observations: int = Field(default=1000, description="Max observations kept in history")
    max_history_age_seconds: float = Field(default=3600.0, description="Max age of observations (seconds)")
    min_trend_observations: int = Field(default=3, description="Minimum observations for trend")
    trend_window_observations: int = Field(default=10, description="Recent observations used for slope")

    # Forecast horizons (minutes)
    forecast_horizons_minutes: List[int] = Field(default=[5, 10, 15])
    min_forecast_observations: int = Field(default=5, description="Min observations before forecasting")

    # Persistence / Hysteresis
    escalation_persistence_frames: int = Field(
        default=2, description="Consecutive evaluations required to escalate risk level"
    )
    recovery_persistence_frames: int = Field(
        default=3, description="Consecutive evaluations required to de-escalate risk level"
    )

    # Idempotency
    idempotency_window_seconds: float = Field(
        default=1.0, description="Window in which duplicate snapshots (same session+ts) are rejected"
    )


default_prediction_settings = PredictionSettings()

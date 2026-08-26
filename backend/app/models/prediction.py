"""
Prediction Database Model — Sprint 10.
"""
from typing import Optional, Dict, Any, List
from pydantic import Field
from app.models.base import BaseDBModel


class PredictionDBModel(BaseDBModel):
    """
    MongoDB document model for predictive crowd risk and recommendation snapshots.
    """
    prediction_id: str = Field(..., description="Unique prediction evaluation identifier")
    session_id: str = Field(..., description="Associated session identifier")
    venue_id: str = Field(..., description="Associated venue identifier")
    timestamp: str = Field(..., description="ISO 8601 evaluation timestamp")
    risk_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Risk score 0-100")
    risk_level: str = Field(default="LOW", description="LOW, GUARDED, ELEVATED, HIGH, CRITICAL")
    factors: List[Dict[str, Any]] = Field(default_factory=list, description="Explainable risk factors")
    trend_direction: str = Field(default="STABLE", description="INCREASING, STABLE, DECREASING, INSUFFICIENT_DATA")
    trend_slope: Optional[float] = Field(default=None, description="Trend slope")
    trend_confidence: str = Field(default="LOW", description="Trend confidence")
    occupancy_forecast: Optional[Dict[str, Any]] = Field(default=None, description="5m/10m/15m occupancy forecasts")
    flow_forecast: Optional[Dict[str, Any]] = Field(default=None, description="Flow rate forecast")
    primary_recommendation: str = Field(default="MONITOR", description="Primary decision action")
    recommendations: List[str] = Field(default_factory=list, description="All applicable recommendations")
    processing_time_ms: float = Field(default=0.0, description="Evaluation duration in ms")

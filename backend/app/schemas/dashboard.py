"""
Dashboard Snapshot Schemas — Sprint 9.

Aggregates existing Sprint 6, 7, and 8 intelligence outputs into a unified
real-time dashboard snapshot DTO.
Zero duplicate business calculations — all values sourced from live engines.

Privacy: NO biometric fields, NO raw images, NO embeddings.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DashboardSnapshotResponse(BaseModel):
    """
    Unified Dashboard Snapshot payload.
    Aggregates session status, occupancy, flow, density, alerts, risk,
    trend, forecasts, decision recommendations, and gate summaries.
    """
    session_id: str = Field(..., description="Monitoring session ID")
    venue_id: str = Field(..., description="Target venue ID")
    session_status: str = Field(..., description="CREATED, ACTIVE, PAUSED, STOPPED, EXPIRED")
    venue_capacity: int = Field(default=1000, description="Configured venue capacity")

    # Occupancy & Flow
    current_occupancy: int = Field(default=0, description="Live physical occupancy")
    occupancy_ratio: float = Field(default=0.0, description="Occupancy relative to capacity/threshold")
    total_entries: int = Field(default=0, description="Cumulative venue entries")
    total_exits: int = Field(default=0, description="Cumulative venue exits")
    net_flow: int = Field(default=0, description="Cumulative entries minus exits")
    entry_rate_5m: float = Field(default=0.0, description="Persons per minute entry rate (5m)")
    exit_rate_5m: float = Field(default=0.0, description="Persons per minute exit rate (5m)")
    net_flow_rate_5m: float = Field(default=0.0, description="Net flow rate persons per minute (5m)")

    # Density & Congestion
    density_level: str = Field(default="LOW", description="LOW, MODERATE, HIGH, CRITICAL")
    congestion_level: str = Field(default="NORMAL", description="NORMAL, BUILDING, CONGESTED, SEVERE_CONGESTION")

    # Alerts & Anomalies
    active_alerts_count: int = Field(default=0)
    active_alerts: List[Dict[str, Any]] = Field(default_factory=list)
    active_anomalies: List[Dict[str, Any]] = Field(default_factory=list)

    # Predictive Risk & Decision (Sprint 8)
    risk_level: Optional[str] = Field(default="LOW", description="LOW, GUARDED, ELEVATED, HIGH, CRITICAL")
    risk_score: Optional[float] = Field(default=0.0, description="Predictive risk score [0, 100]")
    risk_factors: List[Dict[str, Any]] = Field(default_factory=list)
    trend_direction: Optional[str] = Field(default="STABLE", description="INCREASING, STABLE, DECREASING, INSUFFICIENT_DATA")
    trend_slope: Optional[float] = Field(default=None)

    # Forecasts (Sprint 8)
    occupancy_forecast: Optional[Dict[str, Any]] = Field(default=None)
    flow_forecast: Optional[Dict[str, Any]] = Field(default=None)

    # Operational Recommendations (Sprint 8)
    primary_recommendation: Optional[str] = Field(default="MONITOR")
    recommendations: List[str] = Field(default_factory=list)

    # Gate-level summaries
    gate_summaries: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    timestamp: str = Field(..., description="ISO 8601 evaluation timestamp")

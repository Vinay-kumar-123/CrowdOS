"""
Intelligence Schemas — Sprint 9.

Response Pydantic models for Sprint 7 intelligence query endpoints.
Allowlist-based exposure: only operational analytics fields, NO biometric data.

Covers: flow, occupancy, density, dwell, peaks, alerts, anomalies.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------

class FlowMetricsResponse(BaseModel):
    """Venue or gate-level flow metrics response."""
    venue_id: str
    gate_id: Optional[str] = None
    cumulative_entries: int = 0
    cumulative_exits: int = 0
    cumulative_net_flow: int = 0
    entry_rate_1m: float = 0.0
    exit_rate_1m: float = 0.0
    net_flow_rate_1m: float = 0.0
    entry_rate_5m: float = 0.0
    exit_rate_5m: float = 0.0
    net_flow_rate_5m: float = 0.0
    entry_rate_15m: float = 0.0
    exit_rate_15m: float = 0.0
    net_flow_rate_15m: float = 0.0
    entry_rate_60m: float = 0.0
    exit_rate_60m: float = 0.0
    net_flow_rate_60m: float = 0.0


# ---------------------------------------------------------------------------
# Occupancy
# ---------------------------------------------------------------------------

class OccupancySummaryResponse(BaseModel):
    """Venue-level occupancy summary response."""
    venue_id: str
    current_occupancy: int = 0
    total_entries: int = 0
    total_exits: int = 0
    gate_occupancy: Dict[str, int] = Field(default_factory=dict)
    busiest_gate: Optional[str] = None
    least_active_gate: Optional[str] = None
    last_updated: str = ""


# ---------------------------------------------------------------------------
# Density
# ---------------------------------------------------------------------------

class DensityStateResponse(BaseModel):
    """Venue density and congestion state response."""
    venue_id: str
    occupancy: int = 0
    density_level: str = "LOW"
    congestion_level: str = "NORMAL"
    occupancy_ratio: float = 0.0


# ---------------------------------------------------------------------------
# Dwell
# ---------------------------------------------------------------------------

class DwellMetricsResponse(BaseModel):
    """Dwell time metrics response."""
    venue_id: str
    average_dwell: float = 0.0
    median_dwell: float = 0.0
    p95_dwell: float = 0.0
    sample_count: int = 0


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class AlertResponse(BaseModel):
    """Single alert response — privacy-safe allowlist."""
    alert_id: str
    session_id: str
    venue_id: str
    gate_id: Optional[str] = None
    type: str
    severity: str
    status: str
    created_at: str
    last_seen: str
    resolved_at: Optional[str] = None


class AlertListResponse(BaseModel):
    """List of alerts for a venue."""
    venue_id: str
    alerts: List[AlertResponse]
    total: int
    active_count: int


# ---------------------------------------------------------------------------
# Combined intelligence state
# ---------------------------------------------------------------------------

class CurrentIntelligenceResponse(BaseModel):
    """
    Full current intelligence snapshot for a venue.
    Aggregates Sprint 7 outputs.
    """
    venue_id: str
    flow: FlowMetricsResponse
    occupancy: OccupancySummaryResponse
    density: DensityStateResponse
    dwell: DwellMetricsResponse
    active_alerts_count: int = 0
    active_session_id: Optional[str] = None

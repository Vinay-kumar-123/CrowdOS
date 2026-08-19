"""
Session Schemas — Sprint 9.

Request and response Pydantic models for Session lifecycle API endpoints.
Uses allowlist-based field exposure — no passthrough serialization.

Privacy: NO biometric fields, NO raw images, NO embeddings.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class SessionCreateRequest(BaseModel):
    """Request body for POST /api/v1/venues/{venue_id}/sessions"""
    venue_capacity: int = Field(
        default=1000,
        ge=0,
        description="Maximum venue capacity. 0 = unknown (feature_unavailable mode).",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary session metadata (label, operator, event name, etc.)",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class SessionStatusResponse(BaseModel):
    """Single session status response."""
    session_id: str
    venue_id: str
    status: str
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionListResponse(BaseModel):
    """List of sessions for a venue."""
    venue_id: str
    sessions: List[SessionStatusResponse]
    total: int


class SessionActionResponse(BaseModel):
    """Response for start/pause/resume/stop actions."""
    session_id: str
    venue_id: str
    action: str
    success: bool
    status: str
    message: str


class SessionSummaryResponse(BaseModel):
    """
    Session summary returned after stop — immutable snapshot from Sprint 7.
    Allowlist model: only safe operational fields exposed.
    """
    session_id: str
    venue_id: str
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    duration_seconds: float = 0.0
    total_entries: int = 0
    total_exits: int = 0
    peak_occupancy: int = 0
    peak_occupancy_timestamp: Optional[str] = None
    average_entry_rate: float = 0.0
    peak_entry_rate: float = 0.0
    average_exit_rate: float = 0.0
    peak_exit_rate: float = 0.0
    average_dwell: float = 0.0
    median_dwell: float = 0.0
    p95_dwell: float = 0.0
    busiest_gate: Optional[str] = None
    least_active_gate: Optional[str] = None
    peak_congestion: str = "NORMAL"
    total_alerts_created: int = 0
    total_alerts_resolved: int = 0

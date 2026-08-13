"""
SessionSummary Data Model.
Immutable snapshot generated when a MonitoringSession stops.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class SessionSummary(BaseModel):
    """
    Final deterministic summary generated upon session termination.
    """
    session_id: str = Field(...)
    venue_id: str = Field(...)
    started_at: Optional[str] = Field(default=None)
    stopped_at: Optional[str] = Field(default=None)
    duration_seconds: float = Field(default=0.0)

    total_entries: int = Field(default=0)
    total_exits: int = Field(default=0)

    peak_occupancy: int = Field(default=0)
    peak_occupancy_timestamp: Optional[str] = Field(default=None)

    average_entry_rate: float = Field(default=0.0)
    peak_entry_rate: float = Field(default=0.0)

    average_exit_rate: float = Field(default=0.0)
    peak_exit_rate: float = Field(default=0.0)

    average_dwell: float = Field(default=0.0)
    median_dwell: float = Field(default=0.0)
    p95_dwell: float = Field(default=0.0)

    busiest_gate: Optional[str] = Field(default=None)
    least_active_gate: Optional[str] = Field(default=None)

    peak_congestion: str = Field(default="NORMAL")
    total_alerts_created: int = Field(default=0)
    total_alerts_resolved: int = Field(default=0)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

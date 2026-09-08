"""
Visitor API Schemas — Sprint 13.

Pydantic schemas for visitor query responses.
Zero biometric vectors, face crops, or embeddings are exposed.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


def _format_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


class VisitorResponse(BaseModel):
    """Visitor profile summary."""
    visitor_id: str
    venue_id: str
    first_seen: str = Field(..., description="Earliest recorded event timestamp (ISO 8601 UTC)")
    last_seen: str = Field(..., description="Latest recorded event timestamp (ISO 8601 UTC)")
    total_entries: int = Field(default=0, description="Total physical entries recorded")
    total_exits: int = Field(default=0, description="Total physical exits recorded")
    total_visits: int = Field(
        default=0,
        description="Number of valid ENTRY events that created a Visit record, including OPEN visits",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VisitorEventItem(BaseModel):
    """Single historical movement event."""
    visitor_event_id: str
    visitor_id: str
    venue_id: str
    session_id: str
    event_type: str = Field(..., description="'ENTRY' or 'EXIT'")
    gate_id: str
    timestamp: str = Field(..., description="Event timestamp (ISO 8601 UTC)")
    source_event_id: Optional[str] = None
    track_id: Optional[str] = None
    camera_id: Optional[str] = None
    dwell_time: Optional[float] = None


class VisitorEventsListResponse(BaseModel):
    """Paginated timeline of movement events for a visitor."""
    visitor_id: str
    venue_id: str
    total: int
    limit: int
    skip: int
    events: List[VisitorEventItem]


class VisitItem(BaseModel):
    """Single physical presence visit bounded by an ENTRY and matching EXIT."""
    visit_id: str
    visitor_id: str
    venue_id: str
    session_id: str
    entry_event_id: str
    exit_event_id: Optional[str] = None
    entry_time: str = Field(..., description="Entry timestamp (ISO 8601 UTC)")
    exit_time: Optional[str] = Field(default=None, description="Exit timestamp (ISO 8601 UTC)")
    entry_gate: str
    exit_gate: Optional[str] = None
    duration_seconds: Optional[float] = None
    status: str = Field(..., description="'OPEN' or 'COMPLETED'")


class VisitsListResponse(BaseModel):
    """Paginated list of visits for a visitor."""
    visitor_id: str
    venue_id: str
    total: int
    limit: int
    skip: int
    visits: List[VisitItem]


class VisitorHistoryResponse(BaseModel):
    """Consolidated visitor profile, recent visits, and movement event timeline."""
    visitor: VisitorResponse
    recent_visits: List[VisitItem]
    recent_events: List[VisitorEventItem]

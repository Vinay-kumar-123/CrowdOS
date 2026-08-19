"""
Event Ingest Schemas — Sprint 9.

Request and response Pydantic models for event ingest endpoints.
Sprint 6 already implements entry/exit detection internally in ai-engine.
Sprint 9 exposes a REST interface so external producers can push
movement events into the live Intelligence Engine.

Privacy: NO raw video, NO face crops, NO embeddings, NO biometric vectors.
Only gate-level operational metadata is allowed.
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class EventIngestRequest(BaseModel):
    """
    External event ingest payload.
    Maps to Sprint 6 MovementEvent-compatible structure.
    Sprint 6 entry/exit logic is NOT re-implemented here — this is
    purely a transport wrapper that bridges external producers to
    EventIntelligenceEngine.process_event().
    """
    event_type: str = Field(
        ...,
        description="Must be 'ENTRY' or 'EXIT'.",
        examples=["ENTRY", "EXIT"],
    )
    gate_id: str = Field(
        ...,
        description="Gate identifier where the movement was detected.",
        examples=["gate_A", "gate_north"],
    )
    timestamp: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp. If omitted, server time is used.",
    )
    event_id: Optional[str] = Field(
        default=None,
        description="Optional unique event ID for deduplication.",
    )
    dwell_time: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Dwell time in seconds (for EXIT events with journey tracking).",
    )
    # Explicit privacy fence — these fields MUST NOT be present
    # The schema is intentionally restricted (not passthrough).


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class EventIngestResponse(BaseModel):
    """Result of a single event ingest operation."""
    status: str  # "processed" | "ignored" | "rejected" | "error"
    event_type: Optional[str] = None
    gate_id: Optional[str] = None
    reason: Optional[str] = None
    alerts_generated: int = 0
    processing_time_ms: float = 0.0


class VenueInfoResponse(BaseModel):
    """Basic venue info response."""
    venue_id: str
    venue_capacity: int
    ai_engine_available: bool
    active_session_id: Optional[str] = None
    registered_venues: int = 0

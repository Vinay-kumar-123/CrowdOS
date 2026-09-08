"""
Visitor Database Models — Sprint 13.

Defines MongoDB document models for:
- VisitorDBModel: Persistent visitor profile scoped to a venue.
- VisitorEventDBModel: Immutable operational movement event for a visitor.
- VisitDBModel: Physical presence visit bounded by an ENTRY and matching EXIT.

Privacy guarantee:
Zero face embeddings, biometric vectors, face crops, raw frames, or identity tokens
are ever persisted. Strict recursive validation rejects prohibited fields.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union
from pydantic import Field, model_validator
from app.models.base import BaseDBModel, utc_now
from app.models.event import PROHIBITED_BIOMETRIC_FIELDS


def ensure_utc_datetime(val: Union[datetime, str, None]) -> Optional[datetime]:
    """Ensure a timestamp is a timezone-aware UTC datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if isinstance(val, str):
        cleaned = val.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def _assert_no_biometrics_recursive(data: Any, path: str = "") -> None:
    """Recursively enforce that no prohibited biometric field is present."""
    if isinstance(data, dict):
        for k, v in data.items():
            current_path = f"{path}.{k}" if path else str(k)
            if str(k).lower() in PROHIBITED_BIOMETRIC_FIELDS and v is not None:
                raise ValueError(
                    f"PRIVACY VIOLATION: Prohibited biometric field '{k}' found at '{current_path}'."
                )
            _assert_no_biometrics_recursive(v, current_path)
    elif isinstance(data, (list, tuple, set)):
        for idx, item in enumerate(data):
            _assert_no_biometrics_recursive(item, f"{path}[{idx}]")


class VisitorDBModel(BaseDBModel):
    """
    MongoDB document model for a persistent visitor profile.
    Explicitly scoped to (venue_id, visitor_id).
    """
    visitor_id: str = Field(..., description="Unique visitor identifier within venue")
    venue_id: str = Field(..., description="Associated venue identifier")
    first_seen_at: datetime = Field(default_factory=utc_now, description="Earliest recorded event timestamp (UTC)")
    last_seen_at: datetime = Field(default_factory=utc_now, description="Latest recorded event timestamp (UTC)")
    total_entries: int = Field(default=0, ge=0, description="Total physical entries recorded")
    total_exits: int = Field(default=0, ge=0, description="Total physical exits recorded")
    total_visits: int = Field(
        default=0,
        ge=0,
        description="Number of valid ENTRY events that created a Visit record, including OPEN visits",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Safe non-biometric operational metadata")

    @model_validator(mode="before")
    @classmethod
    def validate_visitor_data(cls, data: Any):
        if isinstance(data, dict):
            _assert_no_biometrics_recursive(data)
            if "first_seen_at" in data:
                data["first_seen_at"] = ensure_utc_datetime(data["first_seen_at"])
            if "last_seen_at" in data:
                data["last_seen_at"] = ensure_utc_datetime(data["last_seen_at"])
        return data


class VisitorEventDBModel(BaseDBModel):
    """
    MongoDB document model for an immutable visitor movement event (ENTRY or EXIT).
    """
    visitor_event_id: str = Field(..., description="Unique visitor movement event ID")
    visitor_id: str = Field(..., description="Associated visitor identifier")
    venue_id: str = Field(..., description="Associated venue identifier")
    session_id: str = Field(..., description="Monitoring session identifier")
    event_type: str = Field(..., description="Movement event type: 'ENTRY' or 'EXIT'")
    gate_id: str = Field(..., description="Gate or checkpoint identifier")
    timestamp: datetime = Field(..., description="Event occurrence timestamp (UTC)")
    source_event_id: Optional[str] = Field(default=None, description="Original upstream event_id")
    track_id: Optional[str] = Field(default=None, description="Anonymous tracking reference")
    camera_id: Optional[str] = Field(default=None, description="Camera device identifier")
    dwell_time: Optional[float] = Field(default=None, ge=0.0, description="Dwell time in seconds (for EXIT)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Safe non-biometric metadata")

    @model_validator(mode="before")
    @classmethod
    def validate_event_data(cls, data: Any):
        if isinstance(data, dict):
            _assert_no_biometrics_recursive(data)
            if "timestamp" in data:
                data["timestamp"] = ensure_utc_datetime(data["timestamp"])
            if "event_type" in data and isinstance(data["event_type"], str):
                data["event_type"] = data["event_type"].upper()
        return data


class VisitDBModel(BaseDBModel):
    """
    MongoDB document model representing a physical presence visit.
    Bounded by an ENTRY and matching EXIT.
    """
    visit_id: str = Field(..., description="Unique visit identifier")
    visitor_id: str = Field(..., description="Associated visitor identifier")
    venue_id: str = Field(..., description="Associated venue identifier")
    session_id: str = Field(..., description="Monitoring session identifier where visit started")
    entry_event_id: str = Field(..., description="visitor_event_id of the opening ENTRY")
    exit_event_id: Optional[str] = Field(default=None, description="visitor_event_id of the matching EXIT")
    entry_time: datetime = Field(..., description="Entry timestamp (UTC)")
    exit_time: Optional[datetime] = Field(default=None, description="Exit timestamp (UTC)")
    entry_gate: str = Field(..., description="Gate used for entry")
    exit_gate: Optional[str] = Field(default=None, description="Gate used for exit")
    duration_seconds: Optional[float] = Field(default=None, ge=0.0, description="Total duration in seconds")
    status: str = Field(default="OPEN", description="Visit status: 'OPEN' or 'COMPLETED'")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Safe non-biometric metadata")

    @model_validator(mode="before")
    @classmethod
    def validate_visit_data(cls, data: Any):
        if isinstance(data, dict):
            _assert_no_biometrics_recursive(data)
            if "entry_time" in data:
                data["entry_time"] = ensure_utc_datetime(data["entry_time"])
            if "exit_time" in data and data["exit_time"] is not None:
                data["exit_time"] = ensure_utc_datetime(data["exit_time"])
            if "status" in data and isinstance(data["status"], str):
                data["status"] = data["status"].upper()
        return data

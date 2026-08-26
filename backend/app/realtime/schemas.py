"""
Sprint 11 — Real-Time WebSocket Message Schemas.

Defines standardized Pydantic v2 schemas for all real-time events broadcasted
over WebSockets and Redis Pub/Sub.

Consistent Envelope Format:
{
    "type": "<event_type>",
    "venue_id": "<venue_id>",
    "timestamp": "<ISO-8601 UTC>",
    "data": { ... }
}

Privacy Guarantee:
    Strictly forbids all biometric embeddings, raw frame tensors, face crops,
    or identity tokens in WebSocket payloads.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Generic, TypeVar
from pydantic import BaseModel, Field, model_validator


def utc_iso_now() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


PROHIBITED_BIOMETRIC_FIELDS = {
    "embedding",
    "face_embedding",
    "biometric_vector",
    "raw_vector",
    "face_crop",
    "face_image",
    "raw_frame",
    "raw_video",
    "identity_token",
    "tensor",
}


class WebSocketEventType(str, Enum):
    """Enumeration of all supported real-time WebSocket event types."""
    INITIAL_STATE = "initial_state"
    OCCUPANCY_UPDATE = "occupancy_update"
    FLOW_UPDATE = "flow_update"
    INTELLIGENCE_UPDATE = "intelligence_update"
    ALERT_CREATED = "alert_created"
    ALERT_RESOLVED = "alert_resolved"
    PREDICTION_UPDATE = "prediction_update"
    SESSION_UPDATE = "session_update"
    SYSTEM_STATUS = "system_status"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


T = TypeVar("T")


class WebSocketEnvelope(BaseModel, Generic[T]):
    """
    Standardized top-level WebSocket envelope.
    """
    type: WebSocketEventType = Field(..., description="Real-time event type identifier")
    venue_id: str = Field(..., description="Associated venue identifier")
    timestamp: str = Field(default_factory=utc_iso_now, description="ISO-8601 UTC timestamp")
    data: T = Field(..., description="Typed payload data")

    @model_validator(mode="after")
    def enforce_privacy_rules(self):
        """Recursively ensure zero biometric or raw video fields exist in payload."""
        _validate_no_biometrics(self.data)
        return self


def _validate_no_biometrics(val: Any, path: str = "") -> None:
    """Helper to reject prohibited biometric attributes recursively."""
    if isinstance(val, dict):
        for k, v in val.items():
            current_path = f"{path}.{k}" if path else k
            if k.lower() in PROHIBITED_BIOMETRIC_FIELDS:
                raise ValueError(
                    f"PRIVACY VIOLATION: Prohibited biometric field '{k}' detected at '{current_path}'."
                )
            _validate_no_biometrics(v, current_path)
    elif isinstance(val, list):
        for idx, item in enumerate(val):
            _validate_no_biometrics(item, f"{path}[{idx}]")
    elif hasattr(val, "model_dump"):
        _validate_no_biometrics(val.model_dump(), path)


# ---------------------------------------------------------------------------
# Specific Event Payloads
# ---------------------------------------------------------------------------

class OccupancyUpdatePayload(BaseModel):
    """Payload for occupancy changes."""
    session_id: Optional[str] = None
    current_occupancy: int = 0
    venue_capacity: int = 1000
    occupancy_ratio: float = 0.0
    total_entries: int = 0
    total_exits: int = 0
    net_flow: int = 0
    gate_occupancies: Dict[str, int] = Field(default_factory=dict)


class FlowUpdatePayload(BaseModel):
    """Payload for crowd flow analytics updates."""
    session_id: Optional[str] = None
    entry_rate_1m: float = 0.0
    entry_rate_5m: float = 0.0
    exit_rate_5m: float = 0.0
    net_flow_rate_5m: float = 0.0
    busiest_gate: Optional[str] = None
    gate_flows: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class IntelligenceUpdatePayload(BaseModel):
    """Payload for aggregated crowd intelligence states."""
    session_id: Optional[str] = None
    density_level: str = "LOW"
    congestion_level: str = "NORMAL"
    occupancy: OccupancyUpdatePayload = Field(default_factory=OccupancyUpdatePayload)
    flow: FlowUpdatePayload = Field(default_factory=FlowUpdatePayload)


class AlertEventPayload(BaseModel):
    """Payload for operational alert creation or resolution."""
    alert_id: str
    session_id: Optional[str] = None
    gate_id: Optional[str] = None
    type: str
    severity: str = "MEDIUM"
    status: str = "ACTIVE"
    message: Optional[str] = None
    created_at: str = Field(default_factory=utc_iso_now)
    resolved_at: Optional[str] = None


class PredictionUpdatePayload(BaseModel):
    """Payload for predictive risk, trend, and recommendation updates."""
    session_id: Optional[str] = None
    prediction_id: Optional[str] = None
    risk_score: float = 0.0
    risk_level: str = "LOW"
    trend_direction: str = "STABLE"
    trend_slope: Optional[float] = None
    trend_confidence: str = "LOW"
    primary_recommendation: str = "MONITOR"
    recommendations: List[str] = Field(default_factory=lambda: ["MONITOR"])
    factors: List[Dict[str, Any]] = Field(default_factory=list)
    occupancy_forecast: Optional[Dict[str, Any]] = None
    flow_forecast: Optional[Dict[str, Any]] = None
    processing_time_ms: float = 0.0


class SessionUpdatePayload(BaseModel):
    """Payload for session state machine transitions."""
    session_id: str
    status: str
    action: str = "update"
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    paused_at: Optional[str] = None
    resumed_at: Optional[str] = None
    message: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None


class InitialStatePayload(BaseModel):
    """Payload sent immediately upon WebSocket client connection."""
    venue_id: str
    venue_capacity: int = 1000
    active_session_id: Optional[str] = None
    session_status: Optional[str] = None
    dashboard: Optional[Dict[str, Any]] = None


class SystemStatusPayload(BaseModel):
    """Payload for system health and engine readiness."""
    status: str = "operational"
    database_connected: bool = True
    redis_configured: bool = True
    ai_engine_available: bool = True
    timestamp: str = Field(default_factory=utc_iso_now)

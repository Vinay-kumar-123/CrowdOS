import uuid
from enum import Enum
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from detection.results.schema import BoundingBox


class MovementEventType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    ZONE_CROSSING = "ZONE_CROSSING"


class EventSource(str, Enum):
    TRACK_CROSSING = "TRACK_CROSSING"
    ZONE_CROSSING = "ZONE_CROSSING"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"


class MovementEvent(BaseModel):
    """
    Standardized payload schema for a single movement event (ENTRY, EXIT, or ZONE_CROSSING).
    Preserves complete lineage: camera_id -> gate_id -> track_id -> detection_id -> face_id -> identity_id.
    """
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: MovementEventType = Field(..., description="ENTRY, EXIT, or ZONE_CROSSING")
    camera_id: str = Field(..., description="Camera ID producing the event")
    gate_id: str = Field(..., description="Gate ID associated with the crossing")
    track_id: str = Field(..., description="Sprint 4 Track ID")
    detection_id: str = Field(..., description="Sprint 3 Detection UUID")
    face_id: Optional[str] = Field(default="", description="Sprint 5 Face ID if face visible")
    identity_id: str = Field(default="UNKNOWN", description="Matched identity ID ('UNKNOWN' if unrecognized)")
    identity_status: str = Field(default="UNKNOWN", description="Sprint 5 RecognitionStatus")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    bounding_box: Optional[BoundingBox] = Field(default=None)
    direction: str = Field(default="UNKNOWN", description="ENTRY, EXIT, or UNKNOWN")
    confidence: float = Field(default=1.0, description="Movement event confidence score [0.0, 1.0]")
    event_source: EventSource = Field(default=EventSource.TRACK_CROSSING)
    journey_id: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value if isinstance(self.event_type, MovementEventType) else str(self.event_type),
            "camera_id": self.camera_id,
            "gate_id": self.gate_id,
            "track_id": self.track_id,
            "detection_id": self.detection_id,
            "face_id": self.face_id or "",
            "identity_id": self.identity_id,
            "identity_status": self.identity_status,
            "timestamp": self.timestamp,
            "bounding_box": self.bounding_box.to_list() if self.bounding_box else None,
            "direction": self.direction,
            "confidence": round(self.confidence, 4),
            "event_source": self.event_source.value if isinstance(self.event_source, EventSource) else str(self.event_source),
            "journey_id": self.journey_id,
            "metadata": self.metadata,
        }


class EntryEvent(MovementEvent):
    """
    Specialized MovementEvent payload for ENTRY crossings.
    """
    event_type: MovementEventType = Field(default=MovementEventType.ENTRY)
    entry_gate_id: str = Field(...)
    entry_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    direction: str = Field(default="ENTRY")


class ExitEvent(MovementEvent):
    """
    Specialized MovementEvent payload for EXIT crossings.
    """
    event_type: MovementEventType = Field(default=MovementEventType.EXIT)
    exit_gate_id: str = Field(...)
    exit_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    direction: str = Field(default="EXIT")
    dwell_time: Optional[float] = Field(default=None, description="Calculated dwell time in seconds")

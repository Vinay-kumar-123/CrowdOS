"""
Event Database Model — Sprint 10.

Operational movement event (ENTRY / EXIT) persistence.
Privacy guarantee: NEVER persists face embeddings, biometric vectors, face crops,
raw frames, or identity tokens.
"""
from typing import Optional
from pydantic import Field, model_validator
from app.models.base import BaseDBModel

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
}


class EventDBModel(BaseDBModel):
    """
    MongoDB document model for movement events.
    Captures only operational telemetry: gate, direction, timestamp, non-biometric tracking refs.
    """
    event_id: str = Field(..., description="Unique event identifier")
    venue_id: str = Field(..., description="Associated venue identifier")
    session_id: str = Field(..., description="Associated monitoring session identifier")
    event_type: str = Field(..., description="ENTRY or EXIT")
    gate_id: str = Field(..., description="Gate or checkpoint identifier")
    timestamp: str = Field(..., description="ISO 8601 event timestamp")
    camera_id: Optional[str] = Field(default=None, description="Camera device identifier")
    track_id: Optional[str] = Field(default=None, description="Anonymous tracking track ID")
    detection_id: Optional[str] = Field(default=None, description="Anonymous detection reference")
    dwell_time: Optional[float] = Field(default=None, description="Dwell time in seconds (for EXIT events)")
    status: str = Field(default="processed", description="Ingestion outcome: processed, suppressed, error")
    source: str = Field(default="TRACK_CROSSING", description="Event source origin")

    @model_validator(mode="before")
    @classmethod
    def enforce_privacy_ban(cls, data: any):
        """Strict validation enforcing that zero biometric fields are ever passed to EventDBModel."""
        if isinstance(data, dict):
            for key in PROHIBITED_BIOMETRIC_FIELDS:
                if key in data and data[key] is not None:
                    raise ValueError(f"PRIVACY VIOLATION: Prohibited biometric field '{key}' cannot be persisted.")
        return data

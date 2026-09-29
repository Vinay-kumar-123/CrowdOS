"""
Camera Database Model — Sprint 16.

Defines persistent camera metadata, configuration, runtime health telemetry,
and isolated encrypted credentials for physical RTSP/USB/File cameras.

Privacy Guarantee:
Strictly forbids storage of face embeddings, biometric vectors, raw frames,
raw videos, or identity tokens.
"""
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, Any, Union, Dict
from pydantic import Field, model_validator
from app.models.base import BaseDBModel, utc_now
from app.models.event import PROHIBITED_BIOMETRIC_FIELDS
from app.core.camera_security import sanitize_error_message, sanitize_source_url


class CameraStatus(str, Enum):
    """Lifecycle status of a camera stream."""
    REGISTERED = "REGISTERED"
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    RECONNECTING = "RECONNECTING"
    OFFLINE = "OFFLINE"


def ensure_utc_datetime(val: Union[datetime, str, None]) -> Optional[datetime]:
    """Ensure timestamp is a timezone-aware UTC datetime."""
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


class CameraDBModel(BaseDBModel):
    """
    Persistent document model for a venue camera.
    Sensitive credentials are never stored in plaintext within camera_source;
    credentials_encrypted stores authenticated ciphertext accessible only in-memory at runtime.
    """
    camera_id: str = Field(..., description="Unique camera identifier")
    venue_id: str = Field(..., description="Owning venue identifier")
    camera_name: str = Field(..., description="Human-readable camera label")
    camera_type: str = Field(..., description="Stream type: rtsp, usb, file")
    camera_source: str = Field(..., description="Sanitized connection source (no plaintext credentials)")
    credentials_encrypted: Optional[str] = Field(default=None, description="Encrypted credentials payload")
    gate_id: Optional[str] = Field(default=None, description="Associated venue gate identifier")
    configured_fps: float = Field(default=30.0, description="Target capture frame rate")
    status: CameraStatus = Field(default=CameraStatus.REGISTERED, description="Current lifecycle status")
    last_frame_at: Optional[datetime] = Field(default=None, description="Timestamp of latest received frame")
    last_successful_processing_at: Optional[datetime] = Field(default=None, description="Timestamp of latest processed frame")
    measured_fps: float = Field(default=0.0, description="Rolling measured capture frame rate")
    processing_latency_ms: float = Field(default=0.0, description="Processing latency in milliseconds")
    reconnect_count: int = Field(default=0, description="Number of stream reconnections attempted")
    last_error_at: Optional[datetime] = Field(default=None, description="Timestamp of most recent error")
    last_error_message: Optional[str] = Field(default=None, description="Sanitized description of latest error")
    health_updated_at: Optional[datetime] = Field(default=None, description="Timestamp of latest health update")
    is_active: bool = Field(default=True, description="True if camera is enabled for operation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Safe operational metadata")

    @model_validator(mode="before")
    @classmethod
    def validate_camera_data(cls, data: Any):
        if isinstance(data, dict):
            # 1. Enforce strict privacy ban on biometric fields
            for key in PROHIBITED_BIOMETRIC_FIELDS:
                if key in data and data[key] is not None:
                    raise ValueError(f"PRIVACY VIOLATION: Prohibited field '{key}' cannot be stored on Camera.")

            # 2. Sanitize error messages if present
            if "last_error_message" in data and data["last_error_message"]:
                data["last_error_message"] = sanitize_error_message(data["last_error_message"])

            # 3. Sanitize camera_source so plaintext credentials never persist in camera_source field
            if "camera_source" in data and data["camera_source"]:
                data["camera_source"] = sanitize_source_url(data["camera_source"])

            # 4. Normalize timestamps to UTC
            for tf in ("last_frame_at", "last_successful_processing_at", "last_error_at", "health_updated_at"):
                if tf in data:
                    data[tf] = ensure_utc_datetime(data[tf])

        return data

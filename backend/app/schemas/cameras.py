"""
Camera Schemas — Sprint 16.

Request and response Pydantic models for camera management and health inspection.
Enforces credential masking on all output representations and strict biometric rejection.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator
from app.models.event import PROHIBITED_BIOMETRIC_FIELDS
from app.core.camera_security import sanitize_source_url


class CameraRegisterRequest(BaseModel):
    """Payload to register a new camera for a venue."""
    camera_id: Optional[str] = Field(default=None, description="Optional custom unique camera ID (auto-generated if omitted)")
    camera_name: str = Field(..., min_length=1, max_length=128, description="Human-readable camera name")
    camera_type: str = Field(default="rtsp", description="Camera transport type: rtsp, usb, file")
    camera_source: str = Field(..., min_length=1, description="Camera stream source (RTSP URL, USB device index, or file path)")
    gate_id: Optional[str] = Field(default=None, max_length=64, description="Optional associated venue gate ID")
    configured_fps: float = Field(default=30.0, ge=1.0, le=120.0, description="Target capture FPS")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Safe operational metadata")

    @model_validator(mode="before")
    @classmethod
    def validate_privacy(cls, data: Any):
        if isinstance(data, dict):
            for k in PROHIBITED_BIOMETRIC_FIELDS:
                if k in data and data[k] is not None:
                    raise ValueError(f"PRIVACY VIOLATION: Prohibited field '{k}' not allowed in CameraRegisterRequest.")
            cam_type = data.get("camera_type", "rtsp").lower()
            if cam_type not in ("rtsp", "usb", "file", "ip", "video", "mp4"):
                raise ValueError(f"Unsupported camera_type '{cam_type}'. Allowed: rtsp, usb, file.")
        return data


class CameraResponse(BaseModel):
    """Safe read-only camera metadata representation (credentials strictly masked)."""
    camera_id: str
    venue_id: str
    camera_name: str
    camera_type: str
    camera_source_masked: str = Field(..., description="Sanitized connection source with credentials masked")
    gate_id: Optional[str] = None
    configured_fps: float
    status: str
    last_frame_at: Optional[str] = None
    last_successful_processing_at: Optional[str] = None
    measured_fps: float = 0.0
    processing_latency_ms: float = 0.0
    reconnect_count: int = 0
    health_updated_at: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None


class CameraHealthResponse(BaseModel):
    """Detailed live telemetry and health status for a specific camera."""
    camera_id: str
    venue_id: str
    status: str
    measured_fps: float = 0.0
    processing_latency_ms: float = 0.0
    reconnect_count: int = 0
    last_frame_at: Optional[str] = None
    last_successful_processing_at: Optional[str] = None
    health_score: float = 100.0
    healthy: bool = True
    health_updated_at: Optional[str] = None


class CameraListResponse(BaseModel):
    """List of all registered cameras within a venue."""
    venue_id: str
    cameras: List[CameraResponse]
    total: int


class CameraActionResponse(BaseModel):
    """Result of an operational action on a camera (start, stop)."""
    camera_id: str
    venue_id: str
    action: str
    status: str
    success: bool
    message: str

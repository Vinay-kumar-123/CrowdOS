from enum import Enum
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class CameraEventType(str, Enum):
    CONNECTED = "CAMERA_CONNECTED"
    DISCONNECTED = "CAMERA_DISCONNECTED"
    STARTED = "CAMERA_STARTED"
    STOPPED = "CAMERA_STOPPED"
    RECONNECTING = "CAMERA_RECONNECTING"
    FRAME_RECEIVED = "FRAME_RECEIVED"
    FRAME_DROPPED = "FRAME_DROPPED"
    QUEUE_OVERFLOW = "QUEUE_OVERFLOW"
    BUFFER_FULL = "BUFFER_FULL"
    ERROR = "CAMERA_ERROR"


class CameraEvent(BaseModel):
    """
    Internal camera event model for stream lifecycle and health monitoring.
    """
    event_id: str
    event_type: CameraEventType
    camera_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: Optional[Dict[str, Any]] = None

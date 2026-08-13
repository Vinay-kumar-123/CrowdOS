import uuid
from enum import Enum
from typing import List, Tuple, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from detection.results.schema import BoundingBox


class TrackState(str, Enum):
    """
    Standardized state machine states for person tracklets.
    NEW -> ACTIVE -> LOST -> REIDENTIFIED -> ACTIVE -> REMOVED -> EXPIRED
    """
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    LOST = "LOST"
    REIDENTIFIED = "REIDENTIFIED"
    REMOVED = "REMOVED"
    EXPIRED = "EXPIRED"


class TrackedPerson(BaseModel):
    """
    Standardized payload schema for a single tracked person object.
    Preserves exact detection_id mapping from Sprint 3 Detection Engine.
    """
    track_id: str = Field(..., description="Unique persistent track identifier within camera instance")
    detection_id: str = Field(..., description="Original detection UUID from detection item")
    camera_id: str = Field(..., description="Camera stream ID producing this track")
    frame_number: int = Field(..., description="Frame sequence number")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    bbox: BoundingBox = Field(..., description="Track bounding box [x1, y1, x2, y2]")
    confidence: float = Field(..., description="Detection / Track confidence score between 0.0 and 1.0")
    center: Tuple[float, float] = Field(..., description="Bounding box center (cx, cy)")
    velocity: Tuple[float, float] = Field(default=(0.0, 0.0), description="Pixel velocity per frame (vx, vy)")
    direction_vector: Tuple[float, float] = Field(default=(0.0, 0.0), description="Normalized movement direction unit vector (dx, dy)")
    track_age: int = Field(default=1, description="Total frames since track creation")
    frames_since_update: int = Field(default=0, description="Consecutive frames without detection update")
    track_state: TrackState = Field(default=TrackState.NEW, description="Current track lifecycle state")
    tracker_name: str = Field(default="ByteTrack")
    tracker_version: str = Field(default="1.0.0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track_id": self.track_id,
            "detection_id": self.detection_id,
            "camera_id": self.camera_id,
            "frame_number": self.frame_number,
            "timestamp": self.timestamp,
            "bbox": self.bbox.to_list(),
            "confidence": round(self.confidence, 4),
            "center": [round(self.center[0], 2), round(self.center[1], 2)],
            "velocity": [round(self.velocity[0], 2), round(self.velocity[1], 2)],
            "direction_vector": [round(self.direction_vector[0], 4), round(self.direction_vector[1], 4)],
            "track_age": self.track_age,
            "frames_since_update": self.frames_since_update,
            "track_state": self.track_state.value if isinstance(self.track_state, TrackState) else str(self.track_state),
            "tracker_name": self.tracker_name,
            "tracker_version": self.tracker_version,
        }


class TrackingResult(BaseModel):
    """
    Standardized payload schema for all tracking output in a single frame.
    """
    frame_number: int
    frame_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    camera_id: str
    tracking_time_ms: float
    total_active_tracks: int
    total_lost_tracks: int
    tracks: List[TrackedPerson]
    tracker_name: str = Field(default="ByteTrack")
    tracker_version: str = Field(default="1.0.0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_number": self.frame_number,
            "frame_uuid": self.frame_uuid,
            "timestamp": self.timestamp,
            "camera_id": self.camera_id,
            "tracking_time_ms": round(self.tracking_time_ms, 2),
            "total_active_tracks": self.total_active_tracks,
            "total_lost_tracks": self.total_lost_tracks,
            "tracks": [t.to_dict() for t in self.tracks],
            "tracker_name": self.tracker_name,
            "tracker_version": self.tracker_version,
        }

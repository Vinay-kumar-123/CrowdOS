import uuid
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from detection.results.schema import BoundingBox


class RecognitionStatus(str, Enum):
    """
    Standardized recognition status lifecycle states.
    NO_FACE -> FACE_DETECTED -> QUALITY_REJECTED -> UNKNOWN -> MATCHED / LOW_CONFIDENCE / ERROR
    """
    NO_FACE = "NO_FACE"
    FACE_DETECTED = "FACE_DETECTED"
    QUALITY_REJECTED = "QUALITY_REJECTED"
    UNKNOWN = "UNKNOWN"
    MATCHED = "MATCHED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    ERROR = "ERROR"


class FaceQualityStatus(str, Enum):
    """
    Detailed face crop quality assessment outcomes.
    """
    QUALITY_GOOD = "QUALITY_GOOD"
    QUALITY_POOR = "QUALITY_POOR"
    QUALITY_OCCLUDED = "QUALITY_OCCLUDED"
    QUALITY_TOO_SMALL = "QUALITY_TOO_SMALL"
    QUALITY_BLURRY = "QUALITY_BLURRY"
    QUALITY_LOW_CONFIDENCE = "QUALITY_LOW_CONFIDENCE"


class RecognizedPerson(BaseModel):
    """
    Standardized payload schema for a single recognized person / identity association.
    Preserves complete lineage: detection_id -> track_id -> face_id -> identity_id.

    PRIVACY SAFEGUARD: Raw embedding vectors and face crops are NEVER exposed in this schema.
    """
    recognition_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    camera_id: str = Field(..., description="Camera stream identifier")
    track_id: str = Field(..., description="Sprint 4 Track ID")
    detection_id: str = Field(..., description="Sprint 3 Detection UUID")
    face_id: str = Field(default="", description="Unique face detection UUID if face visible")
    frame_number: int = Field(..., description="Video frame sequence number")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    face_bbox: Optional[BoundingBox] = Field(default=None, description="Face bounding box in frame coordinates")
    face_confidence: float = Field(default=0.0, description="Face detection confidence score")
    face_quality_score: float = Field(default=0.0, description="Face optical quality score [0.0, 1.0]")
    face_quality_status: FaceQualityStatus = Field(default=FaceQualityStatus.QUALITY_POOR)
    identity_id: str = Field(default="UNKNOWN", description="Matched identity identifier ('UNKNOWN' if unrecognised)")
    identity_status: RecognitionStatus = Field(default=RecognitionStatus.NO_FACE)
    similarity_score: float = Field(default=0.0, description="Cosine similarity score [0.0, 1.0]")
    matching_threshold: float = Field(default=0.60, description="Similarity threshold used for match decision")
    recognizer_name: str = Field(default="InsightFace")
    recognizer_version: str = Field(default="5.0.0")
    processing_time_ms: float = Field(default=0.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recognition_id": self.recognition_id,
            "camera_id": self.camera_id,
            "track_id": self.track_id,
            "detection_id": self.detection_id,
            "face_id": self.face_id,
            "frame_number": self.frame_number,
            "timestamp": self.timestamp,
            "face_bbox": self.face_bbox.to_list() if self.face_bbox else None,
            "face_confidence": round(self.face_confidence, 4),
            "face_quality_score": round(self.face_quality_score, 2),
            "face_quality_status": self.face_quality_status.value if isinstance(self.face_quality_status, FaceQualityStatus) else str(self.face_quality_status),
            "identity_id": self.identity_id,
            "identity_status": self.identity_status.value if isinstance(self.identity_status, RecognitionStatus) else str(self.identity_status),
            "similarity_score": round(self.similarity_score, 4),
            "matching_threshold": round(self.matching_threshold, 2),
            "recognizer_name": self.recognizer_name,
            "recognizer_version": self.recognizer_version,
            "processing_time_ms": round(self.processing_time_ms, 2),
        }


class RecognitionResult(BaseModel):
    """
    Standardized payload schema for all recognition and identity associations in a frame.
    """
    frame_number: int
    frame_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    camera_id: str
    total_tracked_persons: int
    total_faces_detected: int
    total_faces_matched: int
    total_faces_unknown: int
    recognition_time_ms: float
    recognized_persons: List[RecognizedPerson]
    recognizer_name: str = Field(default="InsightFace")
    recognizer_version: str = Field(default="5.0.0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_number": self.frame_number,
            "frame_uuid": self.frame_uuid,
            "timestamp": self.timestamp,
            "camera_id": self.camera_id,
            "total_tracked_persons": self.total_tracked_persons,
            "total_faces_detected": self.total_faces_detected,
            "total_faces_matched": self.total_faces_matched,
            "total_faces_unknown": self.total_faces_unknown,
            "recognition_time_ms": round(self.recognition_time_ms, 2),
            "recognized_persons": [r.to_dict() for r in self.recognized_persons],
            "recognizer_name": self.recognizer_name,
            "recognizer_version": self.recognizer_version,
        }

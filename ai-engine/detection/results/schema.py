import uuid
from typing import List, Tuple, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

INFERENCE_ENGINE_VERSION = "3.1.0"


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

    def to_list(self) -> List[float]:
        return [round(self.x1, 2), round(self.y1, 2), round(self.x2, 2), round(self.y2, 2)]


class DetectionItem(BaseModel):
    """
    Standardized schema for a single detected person object.
    """
    detection_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    class_id: int = Field(default=0, description="COCO Class ID (0 = Person)")
    class_name: str = Field(default="person")
    confidence: float = Field(..., description="Detection confidence score between 0.0 and 1.0")
    bbox: BoundingBox
    center: Tuple[float, float]
    width: float
    height: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detection_id": self.detection_id,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": self.bbox.to_list(),
            "center": [round(self.center[0], 2), round(self.center[1], 2)],
            "width": round(self.width, 2),
            "height": round(self.height, 2),
        }


class FrameDetectionResult(BaseModel):
    """
    Standardized payload schema for all detections in a single processed video frame.

    Includes enterprise observability metadata:
    - frame_uuid: unique ID per frame result for distributed tracing
    - model_name: model that produced this result
    - pipeline_version: detection pipeline version
    - inference_engine_version: engine version for auditability
    """
    frame_number: int
    frame_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    camera_id: str
    inference_time_ms: float
    total_persons_detected: int
    detections: List[DetectionItem]
    device_used: str
    resolution: Tuple[int, int]

    # Enterprise observability fields (Task 9)
    model_name: str = Field(default="unknown")
    pipeline_version: str = Field(default="3.1.0")
    inference_engine_version: str = Field(default=INFERENCE_ENGINE_VERSION)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_number": self.frame_number,
            "frame_uuid": self.frame_uuid,
            "timestamp": self.timestamp,
            "camera_id": self.camera_id,
            "inference_time_ms": round(self.inference_time_ms, 2),
            "total_persons_detected": self.total_persons_detected,
            "detections": [d.to_dict() for d in self.detections],
            "device_used": self.device_used,
            "resolution": self.resolution,
            "model_name": self.model_name,
            "pipeline_version": self.pipeline_version,
            "inference_engine_version": self.inference_engine_version,
        }

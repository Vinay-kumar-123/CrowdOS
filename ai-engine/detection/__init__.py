"""
CrowdOS — Sprint 3 Person Detection Engine (Stabilization v3.1).

Public API exports for consuming modules.
"""
from detection.pipeline.detection_pipeline import DetectionPipeline
from detection.engine.detection_engine import DetectionEngine, FrameValidationError
from detection.models.model_manager import ModelManager
from detection.models.base_detector import BaseDetector
from detection.models.yolo_detector import YOLODetector
from detection.processors.result_validator import ResultValidator, ValidationError
from detection.results.schema import FrameDetectionResult, DetectionItem, BoundingBox

__all__ = [
    # Pipeline
    "DetectionPipeline",
    # Engine
    "DetectionEngine",
    "FrameValidationError",
    # Models
    "ModelManager",
    "BaseDetector",
    "YOLODetector",
    # Processors
    "ResultValidator",
    "ValidationError",
    # Schemas
    "FrameDetectionResult",
    "DetectionItem",
    "BoundingBox",
]

__version__ = "3.1.0"
__sprint__ = "Sprint 3 Stabilization — Production-Ready Detection Engine"

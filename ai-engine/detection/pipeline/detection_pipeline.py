from typing import Optional, Callable, Any
import numpy as np
from detection.engine.detection_engine import DetectionEngine
from detection.results.schema import FrameDetectionResult
from detection.utils.logger import detection_logger

PIPELINE_VERSION = "3.1.0"


class DetectionPipeline:
    """
    Modular AI Perception Pipeline encapsulating the end-to-end detection workflow:
    Frame Ingestion -> Preprocessing -> YOLO Inference -> Person Postprocessing -> Result Schema.

    Designed to bind seamlessly to Sprint 2 Camera Infrastructure frame consumer callbacks.
    """
    def __init__(
        self,
        engine: Optional[DetectionEngine] = None,
        result_callback: Optional[Callable] = None,
    ):
        self.engine = engine or DetectionEngine()
        self.result_callback = result_callback

    def initialize(self) -> bool:
        return self.engine.initialize()

    def process_frame(
        self,
        frame: np.ndarray,
        camera_id: str,
        frame_number: int = 0,
    ) -> FrameDetectionResult:
        """
        Executes the detection pipeline on a single frame.
        """
        result = self.engine.detect_persons(
            frame=frame,
            camera_id=camera_id,
            frame_number=frame_number,
        )

        if self.result_callback:
            try:
                self.result_callback(result)
            except Exception as e:
                detection_logger.error(
                    f"Result callback execution error for camera {camera_id}: {e}",
                    extra={"camera_id": camera_id}
                )

        return result

    def get_camera_callback(self) -> Callable:
        """
        Returns a frame consumer callback compatible with Sprint 2 CameraManager:
        `register_camera(..., frame_callback=pipeline.get_camera_callback())`
        """
        def callback(camera_id: str, frame_item: Any) -> FrameDetectionResult:
            frame_matrix = getattr(frame_item, "frame", frame_item)
            frame_num = getattr(frame_item, "frame_number", 0)
            return self.process_frame(
                frame=frame_matrix,
                camera_id=camera_id,
                frame_number=frame_num,
            )
        return callback

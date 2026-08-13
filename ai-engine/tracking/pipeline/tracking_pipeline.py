from typing import Optional, Callable, Any
import numpy as np

from detection.results.schema import FrameDetectionResult
from tracking.engine.tracking_engine import TrackingEngine
from tracking.pipeline.validator import TrackValidator
from tracking.results.schema import TrackingResult
from tracking.utils.logger import tracking_logger

TRACKING_PIPELINE_VERSION = "4.0.0"


class TrackingPipeline:
    """
    Modular Multi-Object Tracking Pipeline encapsulating end-to-end execution:
    Detection Input -> Input Validation -> Tracking Engine -> Track Validation -> Result Payload -> Callback Dispatch.

    Designed to bind seamlessly to Sprint 3 Detection Engine output callbacks.
    """

    def __init__(
        self,
        engine: Optional[TrackingEngine] = None,
        validator: Optional[TrackValidator] = None,
        result_callback: Optional[Callable[[TrackingResult], None]] = None,
    ):
        self.engine = engine or TrackingEngine()
        self.validator = validator or TrackValidator()
        self.result_callback = result_callback

    def initialize(self) -> bool:
        tracking_logger.info(
            f"TrackingPipeline v{TRACKING_PIPELINE_VERSION} initialized successfully"
        )
        return True

    def process_detections(
        self,
        detection_result: FrameDetectionResult,
        frame: Optional[np.ndarray] = None
    ) -> TrackingResult:
        """
        Ingest a FrameDetectionResult payload and produce tracked person outputs.
        """
        # Execute tracking engine update
        tracking_result = self.engine.process_detections(
            detection_result=detection_result,
            frame=frame
        )

        # Validate tracking result payload
        is_valid, errors = self.validator.validate_tracking_result(tracking_result)
        if not is_valid:
            tracking_logger.warning(
                f"TrackingPipeline encountered validation errors on frame {tracking_result.frame_number}: {errors}"
            )

        # Execute downstream subscriber callback
        if self.result_callback:
            try:
                self.result_callback(tracking_result)
            except Exception as e:
                tracking_logger.error(
                    f"Tracking result callback execution error for camera {tracking_result.camera_id}: {e}",
                    extra={"camera_id": tracking_result.camera_id}
                )

        return tracking_result

    def get_detection_callback(self) -> Callable[[FrameDetectionResult], TrackingResult]:
        """
        Returns a detection result consumer callback compatible with Sprint 3 DetectionPipeline:
        `DetectionPipeline(..., result_callback=tracking_pipeline.get_detection_callback())`
        """
        def callback(detection_result: FrameDetectionResult) -> TrackingResult:
            return self.process_detections(detection_result=detection_result)

        return callback

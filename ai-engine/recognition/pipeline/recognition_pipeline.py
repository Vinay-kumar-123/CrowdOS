from typing import Optional, Callable, TYPE_CHECKING
import numpy as np

from tracking.results.schema import TrackingResult
if TYPE_CHECKING:
    from recognition.engine.recognition_engine import RecognitionEngine
from recognition.validation.validator import RecognitionValidator
from recognition.results.schema import RecognitionResult
from recognition.utils.logger import recognition_logger

RECOGNITION_PIPELINE_VERSION = "5.0.0"


class RecognitionPipeline:
    """
    Modular end-to-end Face Recognition & Identity Association Pipeline.

    Architecture:
      TrackingResult + Frame
          ↓
      RecognitionEngine.process_tracking_result()
          ↓
      RecognitionValidator
          ↓
      RecognitionResult
          ↓
      Optional result_callback (Sprint 6 entry point)

    Designed to bind to Sprint 4 TrackingPipeline output callbacks.
    """

    def __init__(
        self,
        engine: RecognitionEngine,
        validator: Optional[RecognitionValidator] = None,
        result_callback: Optional[Callable[[RecognitionResult], None]] = None
    ):
        self.engine = engine
        self.validator = validator or RecognitionValidator()
        self.result_callback = result_callback

    def initialize(self) -> bool:
        recognition_logger.info(
            f"RecognitionPipeline v{RECOGNITION_PIPELINE_VERSION} initialized"
        )
        return True

    def process(
        self,
        tracking_result: TrackingResult,
        frame: np.ndarray
    ) -> RecognitionResult:
        """
        Receive TrackingResult and produce validated RecognitionResult.
        """
        recognition_result = self.engine.process_tracking_result(
            tracking_result=tracking_result,
            frame=frame
        )

        # Validate result schema
        is_valid, errors = self.validator.validate_recognition_result(recognition_result)
        if not is_valid:
            recognition_logger.warning(
                f"RecognitionPipeline validation issues on frame {recognition_result.frame_number}: {errors}"
            )

        # Forward to downstream subscriber (Sprint 6)
        if self.result_callback:
            try:
                self.result_callback(recognition_result)
            except Exception as exc:
                recognition_logger.error(
                    f"Recognition result callback error on camera {recognition_result.camera_id}: {exc}",
                    extra={"camera_id": recognition_result.camera_id}
                )

        return recognition_result

    def get_tracking_callback(self) -> Callable[[TrackingResult], RecognitionResult]:
        """
        Return callback compatible with Sprint 4 TrackingPipeline:
        `TrackingPipeline(..., result_callback=recognition_pipeline.get_tracking_callback())`
        Note: This callback uses a zero-frame (no image) path — use process() directly for full pipeline.
        """
        def callback(tracking_result: TrackingResult) -> RecognitionResult:
            # Synthetic fallback frame for callback-only usage
            blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            return self.process(tracking_result, blank_frame)
        return callback

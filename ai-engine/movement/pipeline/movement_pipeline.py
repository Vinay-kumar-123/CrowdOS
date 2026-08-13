from typing import Optional, Callable, List
from tracking.results.schema import TrackingResult
from recognition.results.schema import RecognitionResult
from movement.engine.movement_engine import MovementEngine
from movement.events.schema import MovementEvent
from movement.utils.logger import movement_logger

MOVEMENT_PIPELINE_VERSION = "6.0.0"


class MovementPipeline:
    """
    End-to-End Movement Intelligence Pipeline Wrapper.
    Binds Sprint 4 TrackingResult + Sprint 5 RecognitionResult to MovementEngine.
    """

    def __init__(
        self,
        engine: MovementEngine,
        event_callback: Optional[Callable[[List[MovementEvent]], None]] = None
    ):
        self.engine = engine
        self.event_callback = event_callback

    def initialize(self) -> bool:
        movement_logger.info(
            f"MovementPipeline v{MOVEMENT_PIPELINE_VERSION} initialized successfully"
        )
        return True

    def process(
        self,
        tracking_result: TrackingResult,
        recognition_result: Optional[RecognitionResult] = None
    ) -> List[MovementEvent]:
        """
        Process single frame tracking + recognition inputs and generate validated movement events.
        """
        events = self.engine.process_frame(
            tracking_result=tracking_result,
            recognition_result=recognition_result
        )

        if events and self.event_callback:
            try:
                self.event_callback(events)
            except Exception as exc:
                movement_logger.error(f"Movement event callback error: {exc}")

        return events

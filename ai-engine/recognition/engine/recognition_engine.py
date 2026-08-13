import time
import threading
from typing import Optional, Dict, Any, List
import numpy as np

from tracking.results.schema import TrackingResult, TrackState, TrackedPerson
from recognition.models.base_recognizer import BaseFaceRecognizer
from recognition.models.base_store import BaseIdentityStore
from recognition.pipeline.temporal import TemporalRecognitionStabilizer
from recognition.engine.metrics import RecognitionMetricsTracker
from recognition.results.schema import (
    RecognitionResult, RecognizedPerson, RecognitionStatus
)
from recognition.utils.logger import recognition_logger
from recognition.config.settings import recognition_settings


class RecognitionEngine:
    """
    Enterprise Multi-Camera Recognition Engine Manager.

    CTO Constraints:
    - Depends ONLY on BaseFaceRecognizer and BaseIdentityStore abstractions.
    - Contains ZERO InsightFace-specific logic.
    - Recognition state is scoped strictly by camera_id + ":" + track_id.
    - Thread-safe across concurrent camera streams.
    """

    def __init__(
        self,
        recognizer: BaseFaceRecognizer,
        identity_store: BaseIdentityStore,
        temporal_confirmation_frames: int = recognition_settings.TEMPORAL_CONFIRMATION_FRAMES
    ):
        self.recognizer = recognizer
        self.identity_store = identity_store
        self.temporal_stabilizer = TemporalRecognitionStabilizer(temporal_confirmation_frames)
        self.metrics = RecognitionMetricsTracker()
        self._lock = threading.Lock()

        recognition_logger.info(
            f"RecognitionEngine initialized with recognizer={recognizer.__class__.__name__}",
            extra={"recognizer_name": recognizer.__class__.__name__}
        )

    def process_tracking_result(
        self,
        tracking_result: TrackingResult,
        frame: np.ndarray
    ) -> RecognitionResult:
        """
        Receive TrackingResult from Sprint 4 and produce RecognitionResult.
        """
        start_time = time.perf_counter()
        camera_id = tracking_result.camera_id
        frame_number = tracking_result.frame_number

        recognized_persons: List[RecognizedPerson] = []
        faces_detected = 0
        faces_rejected = 0
        faces_matched = 0
        faces_unknown = 0
        faces_low_conf = 0
        errors = 0

        # Clean up temporal state for tracks that are REMOVED or EXPIRED
        for track in tracking_result.tracks:
            if track.track_state in (TrackState.REMOVED, TrackState.EXPIRED):
                self.temporal_stabilizer.cleanup_track(camera_id, track.track_id)

        # Process each ACTIVE or REIDENTIFIED tracked person
        active_tracks: List[TrackedPerson] = [
            t for t in tracking_result.tracks
            if t.track_state in (TrackState.ACTIVE, TrackState.REIDENTIFIED, TrackState.NEW)
        ]

        for track in active_tracks:
            person_bbox = [
                track.bbox.x1, track.bbox.y1,
                track.bbox.x2, track.bbox.y2
            ]

            try:
                person_result: RecognizedPerson = self.recognizer.recognize_face_in_track(
                    frame=frame,
                    person_bbox=person_bbox,
                    camera_id=camera_id,
                    track_id=track.track_id,
                    detection_id=track.detection_id,
                    identity_store=self.identity_store,
                    frame_number=frame_number
                )

                # Apply temporal stabilization
                effective_id, effective_status = self.temporal_stabilizer.update(
                    camera_id=camera_id,
                    track_id=track.track_id,
                    identity_id=person_result.identity_id,
                    status=person_result.identity_status
                )

                # Update result with temporally stabilized outcome
                person_result.identity_id = effective_id
                person_result.identity_status = effective_status

                # Count metrics
                if person_result.identity_status == RecognitionStatus.NO_FACE:
                    pass
                elif person_result.identity_status == RecognitionStatus.QUALITY_REJECTED:
                    faces_detected += 1
                    faces_rejected += 1
                elif person_result.identity_status == RecognitionStatus.MATCHED:
                    faces_detected += 1
                    faces_matched += 1
                elif person_result.identity_status == RecognitionStatus.UNKNOWN:
                    faces_detected += 1
                    faces_unknown += 1
                elif person_result.identity_status == RecognitionStatus.LOW_CONFIDENCE:
                    faces_detected += 1
                    faces_low_conf += 1
                elif person_result.identity_status == RecognitionStatus.ERROR:
                    errors += 1

            except Exception as exc:
                recognition_logger.error(
                    f"Recognition error for track {track.track_id} on camera {camera_id}: {exc}",
                    extra={"camera_id": camera_id, "track_id": track.track_id}
                )
                errors += 1
                person_result = RecognizedPerson(
                    camera_id=camera_id,
                    track_id=track.track_id,
                    detection_id=track.detection_id,
                    frame_number=frame_number,
                    identity_status=RecognitionStatus.ERROR
                )

            recognized_persons.append(person_result)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        self.metrics.record_frame(
            persons_processed=len(active_tracks),
            faces_detected=faces_detected,
            faces_rejected=faces_rejected,
            faces_matched=faces_matched,
            faces_unknown=faces_unknown,
            faces_low_conf=faces_low_conf,
            errors=errors,
            recognition_time_ms=elapsed_ms
        )

        return RecognitionResult(
            frame_number=frame_number,
            camera_id=camera_id,
            total_tracked_persons=len(active_tracks),
            total_faces_detected=faces_detected,
            total_faces_matched=faces_matched,
            total_faces_unknown=faces_unknown,
            recognition_time_ms=round(elapsed_ms, 2),
            recognized_persons=recognized_persons,
            recognizer_name=self.recognizer.__class__.__name__,
            recognizer_version=recognition_settings.RECOGNIZER_VERSION,
        )

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "recognizer": self.recognizer.get_info(),
            "identity_store_count": len(self.identity_store.list_identities()),
            "metrics": self.metrics.get_metrics()
        }

    def reset_camera(self, camera_id: str) -> None:
        """Reset temporal state for all tracks of a specific camera."""
        with self._lock:
            # Clean all camera-scoped keys
            keys_to_remove = [
                k for k in self.temporal_stabilizer._states.keys()
                if k.startswith(f"{camera_id}:")
            ]
            for k in keys_to_remove:
                del self.temporal_stabilizer._states[k]

    def reset_all(self) -> None:
        self.temporal_stabilizer.reset_all()
        self.metrics.reset()

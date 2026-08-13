import time
from typing import Dict, Any


class RecognitionMetricsTracker:
    """
    Thread-safe operational metrics collector for the Recognition Engine.
    """

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.total_frames_processed = 0
        self.total_persons_processed = 0
        self.total_faces_detected = 0
        self.total_faces_rejected_quality = 0
        self.total_faces_matched = 0
        self.total_faces_unknown = 0
        self.total_faces_low_confidence = 0
        self.total_errors = 0
        self.total_recognition_time_ms = 0.0
        self.total_detection_time_ms = 0.0
        self.total_embedding_time_ms = 0.0
        self.total_matching_time_ms = 0.0
        self.start_timestamp = time.time()

    def record_frame(
        self,
        persons_processed: int,
        faces_detected: int,
        faces_rejected: int,
        faces_matched: int,
        faces_unknown: int,
        faces_low_conf: int,
        errors: int,
        recognition_time_ms: float
    ) -> None:
        self.total_frames_processed += 1
        self.total_persons_processed += persons_processed
        self.total_faces_detected += faces_detected
        self.total_faces_rejected_quality += faces_rejected
        self.total_faces_matched += faces_matched
        self.total_faces_unknown += faces_unknown
        self.total_faces_low_confidence += faces_low_conf
        self.total_errors += errors
        self.total_recognition_time_ms += recognition_time_ms

    def get_metrics(self) -> Dict[str, Any]:
        avg_lat = (
            self.total_recognition_time_ms / max(1, self.total_frames_processed)
        )
        fps = (1000.0 / avg_lat) if avg_lat > 0 else 0.0
        elapsed = time.time() - self.start_timestamp

        return {
            "total_frames_processed": self.total_frames_processed,
            "total_persons_processed": self.total_persons_processed,
            "total_faces_detected": self.total_faces_detected,
            "total_faces_rejected_quality": self.total_faces_rejected_quality,
            "total_faces_matched": self.total_faces_matched,
            "total_faces_unknown": self.total_faces_unknown,
            "total_faces_low_confidence": self.total_faces_low_confidence,
            "total_errors": self.total_errors,
            "total_recognition_time_ms": round(self.total_recognition_time_ms, 2),
            "average_recognition_latency_ms": round(avg_lat, 2),
            "recognition_fps": round(fps, 2),
            "uptime_seconds": round(elapsed, 2),
        }

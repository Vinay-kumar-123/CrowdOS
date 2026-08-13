import time
from typing import Dict, Any


class MovementMetricsTracker:
    """
    Thread-safe operational metrics collector for the Movement Intelligence Engine.
    """

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.total_frames_processed = 0
        self.total_tracks_processed = 0
        self.total_events_generated = 0
        self.total_entries = 0
        self.total_exits = 0
        self.total_rejected_events = 0
        self.total_duplicate_suppressions = 0
        self.total_processing_time_ms = 0.0
        self.start_timestamp = time.time()

    def record_frame(
        self,
        tracks_processed: int,
        events_generated: int,
        entries: int,
        exits: int,
        rejected: int,
        duplicates: int,
        processing_time_ms: float
    ) -> None:
        self.total_frames_processed += 1
        self.total_tracks_processed += tracks_processed
        self.total_events_generated += events_generated
        self.total_entries += entries
        self.total_exits += exits
        self.total_rejected_events += rejected
        self.total_duplicate_suppressions += duplicates
        self.total_processing_time_ms += processing_time_ms

    def get_metrics(self) -> Dict[str, Any]:
        avg_lat = (
            self.total_processing_time_ms / max(1, self.total_frames_processed)
        )
        fps = (1000.0 / avg_lat) if avg_lat > 0 else 0.0
        elapsed = time.time() - self.start_timestamp

        return {
            "total_frames_processed": self.total_frames_processed,
            "total_tracks_processed": self.total_tracks_processed,
            "total_events_generated": self.total_events_generated,
            "total_entries": self.total_entries,
            "total_exits": self.total_exits,
            "total_rejected_events": self.total_rejected_events,
            "total_duplicate_suppressions": self.total_duplicate_suppressions,
            "total_processing_time_ms": round(self.total_processing_time_ms, 2),
            "average_processing_latency_ms": round(avg_lat, 2),
            "movement_fps": round(fps, 2),
            "uptime_seconds": round(elapsed, 2),
        }

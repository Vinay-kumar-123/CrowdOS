import time
from typing import Dict, Any


class TrackingMetricsTracker:
    """
    Observability & Performance Metrics Collector for the Multi-Object Tracking Engine.
    """

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.total_frames_processed = 0
        self.total_tracking_time_ms = 0.0
        self.total_tracks_created = 0
        self.total_tracks_removed = 0
        self.total_reidentifications = 0
        self.track_lifetimes: list[int] = []
        self.start_timestamp = time.time()

    def record_frame(
        self,
        latency_ms: float,
        active_count: int,
        lost_count: int,
        created_count: int = 0,
        reidentified_count: int = 0
    ) -> None:
        self.total_frames_processed += 1
        self.total_tracking_time_ms += latency_ms
        self.total_tracks_created += created_count
        self.total_reidentifications += reidentified_count

    def record_completed_track(self, lifetime_frames: int) -> None:
        if lifetime_frames > 0:
            self.track_lifetimes.append(lifetime_frames)
            self.total_tracks_removed += 1

    def get_metrics(self) -> Dict[str, Any]:
        avg_latency = (self.total_tracking_time_ms / max(1, self.total_frames_processed))
        fps = (1000.0 / avg_latency) if avg_latency > 0 else 0.0
        avg_lifetime = (
            sum(self.track_lifetimes) / max(1, len(self.track_lifetimes))
            if self.track_lifetimes else 0.0
        )
        elapsed_sec = time.time() - self.start_timestamp

        return {
            "total_frames_processed": self.total_frames_processed,
            "total_tracking_time_ms": round(self.total_tracking_time_ms, 2),
            "average_latency_ms": round(avg_latency, 2),
            "tracking_fps": round(fps, 2),
            "total_tracks_created": self.total_tracks_created,
            "total_tracks_removed": self.total_tracks_removed,
            "total_reidentifications": self.total_reidentifications,
            "average_track_lifetime_frames": round(avg_lifetime, 1),
            "uptime_seconds": round(elapsed_sec, 2),
        }

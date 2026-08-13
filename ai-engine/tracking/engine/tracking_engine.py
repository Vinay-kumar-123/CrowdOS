import threading
from typing import Dict, Any, Optional, Type, Callable
import numpy as np

from detection.results.schema import FrameDetectionResult
from tracking.models.base_tracker import BaseTracker
from tracking.models.bytetrack import ByteTrackTracker
from tracking.results.schema import TrackingResult
from tracking.engine.metrics import TrackingMetricsTracker
from tracking.utils.logger import tracking_logger
from tracking.config.settings import tracking_settings


class TrackingEngine:
    """
    Enterprise Multi-Camera Tracking Engine Manager.

    Responsibilities:
    - Maintains camera-isolated tracker instances (dict[camera_id, BaseTracker])
    - Enforces thread safety across concurrent camera streams using threading locks.
    - Zero tracker algorithm lock-in: depends ONLY on BaseTracker abstract interface.
    - Manages global metrics and per-camera statistics.
    """

    def __init__(
        self,
        default_tracker_type: str = tracking_settings.TRACKER_TYPE,
        custom_tracker_factory: Optional[Callable[[str], BaseTracker]] = None
    ):
        self.default_tracker_type = default_tracker_type
        self.custom_tracker_factory = custom_tracker_factory

        # Camera instance mapping & thread synchronization lock
        self._trackers: Dict[str, BaseTracker] = {}
        self._lock = threading.Lock()

        # Engine metrics
        self.metrics = TrackingMetricsTracker()

        # Registered tracker factories
        self._factories: Dict[str, Callable[[str], BaseTracker]] = {
            "ByteTrack": lambda cam_id: ByteTrackTracker(camera_id=cam_id)
        }

        tracking_logger.info(
            f"TrackingEngine initialized with default tracker '{default_tracker_type}'",
            extra={"tracker_name": default_tracker_type}
        )

    def register_tracker_factory(
        self,
        tracker_type: str,
        factory_fn: Callable[[str], BaseTracker]
    ) -> None:
        """
        Register a new tracker algorithm factory (e.g. DeepSORT, BoTSORT, OC-SORT).
        """
        with self._lock:
            self._factories[tracker_type] = factory_fn
            tracking_logger.info(f"Registered tracker factory for type '{tracker_type}'")

    def get_or_create_tracker(self, camera_id: str) -> BaseTracker:
        """
        Get or instantiate an isolated BaseTracker instance for the specified camera.
        Enforces complete state isolation between cameras.
        """
        with self._lock:
            if camera_id not in self._trackers:
                if self.custom_tracker_factory:
                    tracker = self.custom_tracker_factory(camera_id)
                elif self.default_tracker_type in self._factories:
                    tracker = self._factories[self.default_tracker_type](camera_id)
                else:
                    # Fallback to ByteTrackTracker
                    tracker = ByteTrackTracker(camera_id=camera_id)

                self._trackers[camera_id] = tracker
                tracking_logger.info(
                    f"Created isolated {tracker.__class__.__name__} for camera '{camera_id}'",
                    extra={"camera_id": camera_id, "tracker_name": tracker.__class__.__name__}
                )
            return self._trackers[camera_id]

    def process_detections(
        self,
        detection_result: FrameDetectionResult,
        frame: Optional[np.ndarray] = None
    ) -> TrackingResult:
        """
        Ingest person detections from Sprint 3 Detection Engine and perform tracking.
        Thread-safe delegation to the camera's isolated BaseTracker.
        """
        camera_id = detection_result.camera_id or "default_camera"
        tracker = self.get_or_create_tracker(camera_id)

        # Delegate update to camera-isolated BaseTracker instance
        tracking_result = tracker.update(detection_result, frame)

        # Record metrics
        self.metrics.record_frame(
            latency_ms=tracking_result.tracking_time_ms,
            active_count=tracking_result.total_active_tracks,
            lost_count=tracking_result.total_lost_tracks
        )

        return tracking_result

    def reset_camera(self, camera_id: str) -> bool:
        """
        Reset tracker state for a specific camera stream.
        """
        with self._lock:
            if camera_id in self._trackers:
                self._trackers[camera_id].reset()
                tracking_logger.info(f"Reset tracker state for camera '{camera_id}'")
                return True
            return False

    def remove_camera(self, camera_id: str) -> bool:
        """
        Destroy and purge tracker instance for a decommissioned camera stream.
        """
        with self._lock:
            if camera_id in self._trackers:
                self._trackers[camera_id].destroy()
                del self._trackers[camera_id]
                tracking_logger.info(f"Purged tracker instance for camera '{camera_id}'")
                return True
            return False

    def reset_all(self) -> None:
        """
        Reset all active camera trackers.
        """
        with self._lock:
            for cam_id, tracker in self._trackers.items():
                tracker.reset()
            self.metrics.reset()
            tracking_logger.info("Reset all camera trackers in TrackingEngine")

    def get_statistics(self, camera_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve operational statistics globally or for a specific camera.
        """
        with self._lock:
            if camera_id:
                if camera_id in self._trackers:
                    return self._trackers[camera_id].get_statistics()
                return {"error": f"Camera '{camera_id}' not found"}

            camera_stats = {
                cam_id: tracker.get_statistics()
                for cam_id, tracker in self._trackers.items()
            }
            engine_metrics = self.metrics.get_metrics()
            return {
                "active_cameras_count": len(self._trackers),
                "engine_metrics": engine_metrics,
                "camera_statistics": camera_stats,
            }

    def health_check(self) -> bool:
        """
        Health diagnostic check for TrackingEngine.
        """
        with self._lock:
            for tracker in self._trackers.values():
                if not tracker.health_check():
                    return False
            return True

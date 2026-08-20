from typing import Optional, Tuple, List, Sequence
import numpy as np
from tracking.results.schema import TrackState
from tracking.utils.bounding_box import (
    tlwh_to_tlbr, tlbr_to_tlwh, tlbr_to_cxcyah, cxcyah_to_tlbr,
    calculate_center, calculate_velocity_and_direction
)
from tracking.models.kalman_filter import KalmanFilter


class STrack:
    """
    Single Tracklet representation for multi-object tracking.
    Maintains track identity, bounding box history, Kalman filter state distribution,
    state machine transitions, and velocity estimation.
    """
    _count = 0  # Class fallback ID counter

    def __init__(
        self,
        tlwh: Sequence[float],
        score: float,
        detection_id: str = "",
        camera_id: str = ""
    ):
        # Initial bounding box representation [x1, y1, w, h]
        self._tlwh = np.asarray(tlwh, dtype=np.float32)
        self.score = float(score)
        self.detection_id = detection_id
        self.camera_id = camera_id

        # State Kalman filter distribution
        self.kalman_filter: Optional[KalmanFilter] = None
        self.mean: Optional[np.ndarray] = None
        self.covariance: Optional[np.ndarray] = None

        # Track identity and state
        self.track_id: str = ""
        self.track_state: TrackState = TrackState.NEW
        self.is_activated: bool = False

        # History and lifetime metrics
        self.frame_id: int = 0
        self.start_frame: int = 0
        self.tracklet_len: int = 0
        self.time_since_update: int = 0

        # Trajectory history for velocity computation
        self.center_history: List[Tuple[float, float]] = []

    @classmethod
    def next_id(cls) -> int:
        cls._count += 1
        return cls._count

    @classmethod
    def reset_counter(cls) -> None:
        cls._count = 0

    @property
    def tlwh(self) -> np.ndarray:
        """
        Get current bounding box in [x1, y1, w, h] format.
        If Kalman filter active, derived from mean state.
        """
        if self.mean is None:
            return self._tlwh.copy()
        ret = self.mean[:4].copy()
        ret[2] *= ret[3]  # w = aspect_ratio * height
        ret[:2] -= ret[2:] / 2.0  # top_left_x = cx - w/2
        return ret

    @property
    def tlbr(self) -> np.ndarray:
        """
        Get current bounding box in [x1, y1, x2, y2] format.
        """
        return tlwh_to_tlbr(self.tlwh)

    @property
    def cxcyah(self) -> np.ndarray:
        """
        Get bounding box in center format [cx, cy, aspect, height].
        """
        return tlbr_to_cxcyah(self.tlbr)

    @property
    def center(self) -> Tuple[float, float]:
        """
        Current center point (cx, cy).
        """
        box = self.tlbr
        return calculate_center([float(box[0]), float(box[1]), float(box[2]), float(box[3])])

    @property
    def velocity_and_direction(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """
        Calculate pixel velocity (vx, vy) and direction unit vector (dx, dy).
        """
        if len(self.center_history) < 2:
            return ((0.0, 0.0), (0.0, 0.0))
        curr_center = self.center_history[-1]
        prev_center = self.center_history[-2]
        return calculate_velocity_and_direction(curr_center, prev_center, dt_frames=1)

    def predict(self) -> None:
        """
        Advance state mean and covariance via Kalman filter prediction.
        """
        if self.mean is not None and self.covariance is not None and self.kalman_filter is not None:
            if self.track_state != TrackState.ACTIVE:
                self.mean[7] = 0.0  # Zero velocity on lost tracks
            self.mean, self.covariance = self.kalman_filter.predict(self.mean, self.covariance)

    def activate(
        self,
        kalman_filter: KalmanFilter,
        frame_id: int,
        track_id: Optional[str] = None
    ) -> None:
        """
        Activate new track with Kalman filter initialization.
        """
        self.kalman_filter = kalman_filter
        self.track_id = track_id if track_id is not None else str(self.next_id())
        self.mean, self.covariance = self.kalman_filter.initiate(self.cxcyah)

        self.tracklet_len = 0
        self.track_state = TrackState.ACTIVE
        self.is_activated = True
        self.frame_id = frame_id
        self.start_frame = frame_id
        self.time_since_update = 0
        self.center_history.append(self.center)

    def re_activate(
        self,
        new_track: "STrack",
        frame_id: int,
        new_id: bool = False
    ) -> None:
        """
        Re-activate a lost track upon re-observation in a subsequent frame.
        Transitions state from LOST -> REIDENTIFIED -> ACTIVE.
        """
        if self.kalman_filter is None:
            self.kalman_filter = KalmanFilter()
            self.mean, self.covariance = self.kalman_filter.initiate(new_track.cxcyah)
        else:
            self.mean, self.covariance = self.kalman_filter.update(
                self.mean, self.covariance, new_track.cxcyah
            )

        self._tlwh = new_track._tlwh.copy()
        self.score = new_track.score
        self.detection_id = new_track.detection_id
        self.tracklet_len = 0
        self.track_state = TrackState.REIDENTIFIED
        self.is_activated = True
        self.frame_id = frame_id
        self.time_since_update = 0
        if new_id:
            self.track_id = str(self.next_id())
        self.center_history.append(self.center)

    def update(self, new_track: "STrack", frame_id: int) -> None:
        """
        Update active track state with new observation bounding box.
        """
        self.frame_id = frame_id
        self.tracklet_len += 1
        self.time_since_update = 0

        new_cxcyah = new_track.cxcyah
        if self.kalman_filter is not None and self.mean is not None and self.covariance is not None:
            self.mean, self.covariance = self.kalman_filter.update(
                self.mean, self.covariance, new_cxcyah
            )
        else:
            self._tlwh = new_track._tlwh.copy()

        self.score = new_track.score
        self.detection_id = new_track.detection_id
        self.track_state = TrackState.ACTIVE
        self.is_activated = True
        self.center_history.append(self.center)
        if len(self.center_history) > 30:
            self.center_history.pop(0)

    def mark_lost(self) -> None:
        """
        Mark track as lost (missing in current frame).
        """
        self.track_state = TrackState.LOST

    def mark_removed(self) -> None:
        """
        Mark track for removal.
        """
        self.track_state = TrackState.REMOVED

    def mark_expired(self) -> None:
        """
        Mark track as expired (purged from memory).
        """
        self.track_state = TrackState.EXPIRED

    def to_dict(self) -> dict:
        box = self.tlbr
        vel, dir_vec = self.velocity_and_direction
        return {
            "track_id": self.track_id,
            "detection_id": self.detection_id,
            "camera_id": self.camera_id,
            "frame_number": self.frame_id,
            "bbox": [round(float(box[0]), 2), round(float(box[1]), 2), round(float(box[2]), 2), round(float(box[3]), 2)],
            "confidence": round(self.score, 4),
            "track_state": self.track_state.value if isinstance(self.track_state, TrackState) else str(self.track_state),
            "track_age": self.frame_id - self.start_frame + 1,
            "frames_since_update": self.time_since_update,
            "velocity": vel,
            "direction_vector": dir_vec,
        }

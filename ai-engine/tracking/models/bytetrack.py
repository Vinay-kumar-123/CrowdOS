import time
from typing import Optional, List, Dict, Any
import numpy as np
from detection.results.schema import FrameDetectionResult, BoundingBox
from tracking.models.base_tracker import BaseTracker
from tracking.models.kalman_filter import KalmanFilter
from tracking.models.track_state import STrack
from tracking.results.schema import TrackState, TrackedPerson, TrackingResult
from tracking.utils.matching import linear_assignment, iou_distance
from tracking.utils.bounding_box import tlbr_to_tlwh, calculate_center
from tracking.utils.logger import tracking_logger
from tracking.config.settings import tracking_settings


class ByteTrackTracker(BaseTracker):
    """
    Faithful implementation of the two-stage ByteTrack multi-object tracking algorithm.
    Inherits from BaseTracker.

    Features:
    - 8D Kalman Filter for motion prediction
    - 1st Stage Association: High-confidence detections matched against active track predictions via IoU distance.
    - 2nd Stage Association: Low-confidence detections matched against remaining unmatched active tracks to maintain continuity during partial occlusions.
    - Full track lifecycle state machine (NEW -> ACTIVE -> LOST -> REIDENTIFIED -> REMOVED -> EXPIRED).
    """

    def __init__(
        self,
        track_thresh: float = tracking_settings.TRACK_THRESH,
        min_confidence: float = tracking_settings.MIN_CONFIDENCE,
        match_thresh: float = tracking_settings.MATCH_THRESHOLD,
        low_match_thresh: float = tracking_settings.LOW_MATCH_THRESHOLD,
        max_lost_frames: int = tracking_settings.MAX_LOST_FRAMES,
        camera_id: str = "default_camera"
    ):
        self.track_thresh = track_thresh
        self.min_confidence = min_confidence
        self.match_thresh = match_thresh
        self.low_match_thresh = low_match_thresh
        self.max_lost_frames = max_lost_frames
        self.camera_id = camera_id

        self.kalman_filter = KalmanFilter()
        self.tracked_stracks: List[STrack] = []
        self.lost_stracks: List[STrack] = []
        self.removed_stracks: List[STrack] = []

        self.frame_id = 0
        self.id_counter = 0
        self._is_initialized = False

        # Performance counters
        self.total_tracks_created = 0
        self.total_reidentifications = 0
        self.total_associations_ms = 0.0

        self.initialize()

    def initialize(self) -> bool:
        self.tracked_stracks = []
        self.lost_stracks = []
        self.removed_stracks = []
        self.frame_id = 0
        self.id_counter = 0
        self._is_initialized = True
        tracking_logger.info(
            f"Initialized ByteTrackTracker for camera {self.camera_id}",
            extra={"camera_id": self.camera_id, "tracker_name": "ByteTrack"}
        )
        return True

    def _next_track_id(self) -> str:
        self.id_counter += 1
        return str(self.id_counter)

    def update(
        self,
        detection_result: FrameDetectionResult,
        frame: Optional[np.ndarray] = None
    ) -> TrackingResult:
        start_time = time.perf_counter()
        self.frame_id += 1
        cam_id = detection_result.camera_id or self.camera_id

        # Parse detections
        detections_high: List[STrack] = []
        detections_low: List[STrack] = []

        for item in detection_result.detections:
            bbox = item.bbox
            tlbr = [bbox.x1, bbox.y1, bbox.x2, bbox.y2]
            tlwh = tlbr_to_tlwh(tlbr)
            conf = float(item.confidence)

            if conf >= self.track_thresh:
                det = STrack(tlwh, conf, detection_id=item.detection_id, camera_id=cam_id)
                detections_high.append(det)
            elif conf >= self.min_confidence:
                det = STrack(tlwh, conf, detection_id=item.detection_id, camera_id=cam_id)
                detections_low.append(det)

        # Classify current tracks
        unconfirmed_stracks: List[STrack] = []
        tracked_stracks: List[STrack] = []

        for track in self.tracked_stracks:
            if not track.is_activated:
                unconfirmed_stracks.append(track)
            else:
                tracked_stracks.append(track)

        strack_pool = tracked_stracks + self.lost_stracks

        # Predict Kalman states
        for track in strack_pool:
            track.predict()
        for track in unconfirmed_stracks:
            track.predict()

        # --- 1st STAGE ASSOCIATION (High Confidence Detections) ---
        dists = iou_distance(strack_pool, detections_high)
        matches_1, u_track_1_idx, u_det_1_idx = linear_assignment(dists, thresh=self.match_thresh)

        activated_stracks: List[STrack] = []
        refind_stracks: List[STrack] = []

        for itrack, idet in matches_1:
            track = strack_pool[itrack]
            det = detections_high[idet]
            if track.track_state == TrackState.ACTIVE:
                track.update(det, self.frame_id)
                activated_stracks.append(track)
            else:
                # Recover lost track -> REIDENTIFIED
                track.re_activate(det, self.frame_id, new_id=False)
                refind_stracks.append(track)
                self.total_reidentifications += 1
                tracking_logger.info(
                    f"Track ID {track.track_id} re-identified in camera {cam_id}",
                    extra={
                        "track_id": track.track_id,
                        "camera_id": cam_id,
                        "state_transition": "LOST->REIDENTIFIED->ACTIVE",
                        "frame_number": self.frame_id
                    }
                )
                track.track_state = TrackState.ACTIVE

        # --- 2nd STAGE ASSOCIATION (Low Confidence Detections) ---
        # Match remaining active tracks with low confidence detections
        u_tracks_after_stage1 = [strack_pool[i] for i in u_track_1_idx if strack_pool[i].track_state == TrackState.ACTIVE]
        dists_low = iou_distance(u_tracks_after_stage1, detections_low)
        matches_2, u_track_2_idx, u_det_2_idx = linear_assignment(dists_low, thresh=self.low_match_thresh)

        for itrack, idet in matches_2:
            track = u_tracks_after_stage1[itrack]
            det = detections_low[idet]
            track.update(det, self.frame_id)
            activated_stracks.append(track)

        # Unmatched active tracks become LOST
        for idx in u_track_2_idx:
            track = u_tracks_after_stage1[idx]
            if track.track_state != TrackState.LOST:
                track.mark_lost()
                track.time_since_update += 1
                self.lost_stracks.append(track)
                tracking_logger.info(
                    f"Track ID {track.track_id} lost in camera {cam_id}",
                    extra={
                        "track_id": track.track_id,
                        "camera_id": cam_id,
                        "state_transition": "ACTIVE->LOST",
                        "frame_number": self.frame_id
                    }
                )

        # --- 3rd STAGE ASSOCIATION (Unconfirmed Tracks with Unmatched High-Conf Detections) ---
        u_detections_high = [detections_high[i] for i in u_det_1_idx]
        dists_unconfirmed = iou_distance(unconfirmed_stracks, u_detections_high)
        matches_3, u_unconfirmed_idx, u_det_high_final_idx = linear_assignment(
            dists_unconfirmed, thresh=tracking_settings.UNCONFIRMED_MATCH_THRESHOLD
        )

        for itrack, idet in matches_3:
            track = unconfirmed_stracks[itrack]
            det = u_detections_high[idet]
            track.update(det, self.frame_id)
            track.is_activated = True
            activated_stracks.append(track)

        for idx in u_unconfirmed_idx:
            track = unconfirmed_stracks[idx]
            track.mark_removed()
            self.removed_stracks.append(track)

        # --- INITIALIZE NEW TRACKS ---
        for idx in u_det_high_final_idx:
            det = u_detections_high[idx]
            if det.score >= self.track_thresh:
                new_id = self._next_track_id()
                det.activate(self.kalman_filter, self.frame_id, track_id=new_id)
                activated_stracks.append(det)
                self.total_tracks_created += 1
                tracking_logger.info(
                    f"Track ID {new_id} created in camera {cam_id}",
                    extra={
                        "track_id": new_id,
                        "camera_id": cam_id,
                        "state_transition": "NEW->ACTIVE",
                        "frame_number": self.frame_id
                    }
                )

        # --- UPDATE TRACK LISTS & HANDLE EXPIRATIONS ---
        new_lost_stracks: List[STrack] = []
        for track in self.lost_stracks:
            if track in refind_stracks or track in activated_stracks:
                continue
            track.time_since_update += 1
            if self.frame_id - track.frame_id > self.max_lost_frames:
                track.mark_removed()
                track.mark_expired()
                self.removed_stracks.append(track)
                tracking_logger.info(
                    f"Track ID {track.track_id} expired and removed in camera {cam_id}",
                    extra={
                        "track_id": track.track_id,
                        "camera_id": cam_id,
                        "state_transition": "LOST->REMOVED->EXPIRED",
                        "frame_number": self.frame_id
                    }
                )
            else:
                new_lost_stracks.append(track)

        self.lost_stracks = new_lost_stracks
        self.tracked_stracks = [t for t in (activated_stracks + refind_stracks) if t.track_state == TrackState.ACTIVE or t.track_state == TrackState.REIDENTIFIED]

        # Prepare tracked output payload items
        output_person_items: List[TrackedPerson] = []
        for track in self.tracked_stracks:
            box = track.tlbr
            cx, cy = track.center
            vel, dir_vec = track.velocity_and_direction

            tracked_person = TrackedPerson(
                track_id=track.track_id,
                detection_id=track.detection_id,
                camera_id=cam_id,
                frame_number=self.frame_id,
                timestamp=detection_result.timestamp,
                bbox=BoundingBox(x1=float(box[0]), y1=float(box[1]), x2=float(box[2]), y2=float(box[3])),
                confidence=round(float(track.score), 4),
                center=(cx, cy),
                velocity=vel,
                direction_vector=dir_vec,
                track_age=self.frame_id - track.start_frame + 1,
                frames_since_update=track.time_since_update,
                track_state=track.track_state,
                tracker_name="ByteTrack",
                tracker_version=tracking_settings.TRACKER_VERSION,
            )
            output_person_items.append(tracked_person)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self.total_associations_ms += elapsed_ms

        result = TrackingResult(
            frame_number=detection_result.frame_number,
            camera_id=cam_id,
            tracking_time_ms=round(elapsed_ms, 2),
            total_active_tracks=len(output_person_items),
            total_lost_tracks=len(self.lost_stracks),
            tracks=output_person_items,
            tracker_name="ByteTrack",
            tracker_version=tracking_settings.TRACKER_VERSION,
        )

        return result

    def reset(self) -> None:
        self.initialize()

    def destroy(self) -> None:
        self.tracked_stracks.clear()
        self.lost_stracks.clear()
        self.removed_stracks.clear()
        self._is_initialized = False

    def get_statistics(self) -> Dict[str, Any]:
        avg_assoc = (self.total_associations_ms / max(1, self.frame_id))
        return {
            "camera_id": self.camera_id,
            "tracker_name": "ByteTrack",
            "processed_frames": self.frame_id,
            "active_tracks_count": len(self.tracked_stracks),
            "lost_tracks_count": len(self.lost_stracks),
            "total_tracks_created": self.total_tracks_created,
            "total_reidentifications": self.total_reidentifications,
            "average_association_time_ms": round(avg_assoc, 3),
            "is_initialized": self._is_initialized,
        }

    def health_check(self) -> bool:
        return self._is_initialized

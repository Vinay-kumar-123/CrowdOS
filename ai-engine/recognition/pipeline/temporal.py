import threading
from collections import deque
from typing import Dict, Optional, Deque
from recognition.results.schema import RecognitionStatus


class TrackRecognitionState:
    """
    Per-track temporal recognition state buffer.
    Maintains a sliding window of recent recognition results for stabilization.
    """

    def __init__(self, confirmation_frames: int = 3):
        self.confirmation_frames = max(1, confirmation_frames)
        # Deque of (identity_id, status) tuples from recent frames
        self.history: Deque[tuple[str, RecognitionStatus]] = deque(maxlen=confirmation_frames)
        self.stable_identity_id: Optional[str] = None
        self.stable_status: RecognitionStatus = RecognitionStatus.UNKNOWN
        self.is_stable: bool = False

    def update(self, identity_id: str, status: RecognitionStatus) -> tuple[str, RecognitionStatus]:
        """
        Update temporal state with new recognition observation.

        CTO Rules:
        1. A low-quality/missing face (NO_FACE, QUALITY_REJECTED, ERROR) must NEVER
           overwrite a previously established stable identity with a different identity.
        2. UNKNOWN is always a valid result.
        3. Stabilization only occurs after TEMPORAL_CONFIRMATION_FRAMES consistent MATCHED observations.

        Returns the effective (identity_id, status) after applying temporal policy.
        """
        # If current observation is non-face / quality rejected / error, preserve stable state
        if status in (RecognitionStatus.NO_FACE, RecognitionStatus.QUALITY_REJECTED, RecognitionStatus.ERROR):
            if self.is_stable:
                # Preserve established identity — do not overwrite on bad frame
                return self.stable_identity_id, self.stable_status
            return identity_id, status

        # Record new observation
        self.history.append((identity_id, status))

        # Check for temporal stabilization: requires consecutive MATCHED frames for same identity
        if status == RecognitionStatus.MATCHED and len(self.history) >= self.confirmation_frames:
            recent_ids = [h[0] for h in self.history]
            recent_statuses = [h[1] for h in self.history]

            if (all(rid == identity_id for rid in recent_ids) and
                    all(s == RecognitionStatus.MATCHED for s in recent_statuses)):
                self.stable_identity_id = identity_id
                self.stable_status = RecognitionStatus.MATCHED
                self.is_stable = True

        return identity_id, status

    def reset(self) -> None:
        """Reset track temporal state (called when track is REMOVED/EXPIRED)."""
        self.history.clear()
        self.stable_identity_id = None
        self.stable_status = RecognitionStatus.UNKNOWN
        self.is_stable = False


class TemporalRecognitionStabilizer:
    """
    Thread-safe temporal recognition stabilization manager.
    State is scoped by camera_id + ":" + track_id.

    CTO Constraint: NEVER shares recognition state across cameras.
    """

    def __init__(self, confirmation_frames: int = 3):
        self.confirmation_frames = confirmation_frames
        self._states: Dict[str, TrackRecognitionState] = {}
        self._lock = threading.Lock()

    def _make_key(self, camera_id: str, track_id: str) -> str:
        return f"{camera_id}:{track_id}"

    def update(
        self,
        camera_id: str,
        track_id: str,
        identity_id: str,
        status: RecognitionStatus
    ) -> tuple[str, RecognitionStatus]:
        """
        Update temporal stabilizer and return effective (identity_id, status).
        """
        key = self._make_key(camera_id, track_id)

        with self._lock:
            if key not in self._states:
                self._states[key] = TrackRecognitionState(self.confirmation_frames)

            return self._states[key].update(identity_id, status)

    def cleanup_track(self, camera_id: str, track_id: str) -> None:
        """
        Remove temporal state for a track that has been permanently removed/expired.
        """
        key = self._make_key(camera_id, track_id)
        with self._lock:
            if key in self._states:
                self._states[key].reset()
                del self._states[key]

    def is_stable(self, camera_id: str, track_id: str) -> bool:
        key = self._make_key(camera_id, track_id)
        with self._lock:
            state = self._states.get(key)
            return state.is_stable if state else False

    def get_stable_identity(self, camera_id: str, track_id: str) -> Optional[str]:
        key = self._make_key(camera_id, track_id)
        with self._lock:
            state = self._states.get(key)
            return state.stable_identity_id if (state and state.is_stable) else None

    def reset_all(self) -> None:
        with self._lock:
            self._states.clear()

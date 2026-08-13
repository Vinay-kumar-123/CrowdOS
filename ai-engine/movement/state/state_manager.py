import threading
from typing import Dict, Optional, List
from movement.state.movement_state import TrackMovementState, MovementState


class MovementStateManager:
    """
    Thread-safe Movement State Machine Manager.
    State is strictly scoped by camera_id + ":" + gate_id + ":" + track_id.
    """

    def __init__(
        self,
        trajectory_window: int = 8,
        max_lost_frames: int = 30
    ):
        self.trajectory_window = trajectory_window
        self.max_lost_frames = max_lost_frames
        self._states: Dict[str, TrackMovementState] = {}
        self._lock = threading.Lock()

    def _make_key(self, camera_id: str, gate_id: str, track_id: str) -> str:
        return f"{camera_id}:{gate_id}:{track_id}"

    def get_or_create_state(
        self,
        camera_id: str,
        gate_id: str,
        track_id: str
    ) -> TrackMovementState:
        key = self._make_key(camera_id, gate_id, track_id)
        with self._lock:
            if key not in self._states:
                self._states[key] = TrackMovementState(
                    camera_id=camera_id,
                    gate_id=gate_id,
                    track_id=track_id,
                    trajectory_window=self.trajectory_window,
                    max_lost_frames=self.max_lost_frames
                )
            return self._states[key]

    def get_state(self, camera_id: str, gate_id: str, track_id: str) -> Optional[TrackMovementState]:
        key = self._make_key(camera_id, gate_id, track_id)
        with self._lock:
            return self._states.get(key)

    def mark_missing_tracks(self, camera_id: str, gate_id: str, active_track_ids: List[str]) -> List[str]:
        """
        Mark tracks missing from current frame as LOST.
        Returns list of track_ids that have EXPIRED after exceeding max_lost_frames.
        """
        prefix = f"{camera_id}:{gate_id}:"
        expired_keys: List[str] = []

        with self._lock:
            for key, state in list(self._states.items()):
                if key.startswith(prefix):
                    if state.track_id not in active_track_ids:
                        state.mark_lost()
                        if state.is_expired():
                            state.transition_to(MovementState.EXPIRED)
                            expired_keys.append(key)

            for key in expired_keys:
                del self._states[key]

        return [k.split(":")[-1] for k in expired_keys]

    def cleanup_track(self, camera_id: str, gate_id: str, track_id: str) -> None:
        key = self._make_key(camera_id, gate_id, track_id)
        with self._lock:
            if key in self._states:
                del self._states[key]

    def clear(self) -> None:
        with self._lock:
            self._states.clear()

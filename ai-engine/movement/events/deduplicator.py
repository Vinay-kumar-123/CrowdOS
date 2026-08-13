import time
import threading
from typing import Dict, Optional
from movement.config.settings import movement_settings
from movement.utils.logger import movement_logger


class EventDeduplicator:
    """
    Thread-safe Movement Event Deduplicator.
    Suppresses duplicate ENTRY / EXIT events for the same active track or identity within a sliding window.
    """

    def __init__(self, window_seconds: float = movement_settings.EVENT_DEDUP_WINDOW):
        self.window_seconds = window_seconds
        self._history: Dict[str, float] = {}
        self._lock = threading.Lock()

    def _make_track_key(self, camera_id: str, gate_id: str, track_id: str, event_type: str) -> str:
        return f"track:{camera_id}:{gate_id}:{track_id}:{event_type}"

    def _make_identity_key(self, gate_id: str, identity_id: str, event_type: str) -> str:
        return f"identity:{gate_id}:{identity_id}:{event_type}"

    def is_duplicate(
        self,
        camera_id: str,
        gate_id: str,
        track_id: str,
        event_type: str,
        identity_id: str = "UNKNOWN",
        current_time: Optional[float] = None
    ) -> bool:
        now = current_time if current_time is not None else time.time()
        track_key = self._make_track_key(camera_id, gate_id, track_id, event_type)

        with self._lock:
            # 1. Check track-level deduplication
            if track_key in self._history:
                last_time = self._history[track_key]
                if (now - last_time) < self.window_seconds:
                    movement_logger.info(
                        f"Suppressed duplicate track event: key={track_key} ({now - last_time:.2f}s < {self.window_seconds}s)"
                    )
                    return True

            # 2. Check identity-level deduplication (for known identities)
            if identity_id and identity_id != "UNKNOWN":
                identity_key = self._make_identity_key(gate_id, identity_id, event_type)
                if identity_key in self._history:
                    last_time = self._history[identity_key]
                    if (now - last_time) < self.window_seconds:
                        movement_logger.info(
                            f"Suppressed duplicate identity event: key={identity_key} ({now - last_time:.2f}s < {self.window_seconds}s)"
                        )
                        return True

        return False

    def record_event(
        self,
        camera_id: str,
        gate_id: str,
        track_id: str,
        event_type: str,
        identity_id: str = "UNKNOWN",
        current_time: Optional[float] = None
    ) -> None:
        now = current_time if current_time is not None else time.time()
        track_key = self._make_track_key(camera_id, gate_id, track_id, event_type)

        with self._lock:
            self._history[track_key] = now
            if identity_id and identity_id != "UNKNOWN":
                identity_key = self._make_identity_key(gate_id, identity_id, event_type)
                self._history[identity_key] = now

            # Clean expired entries
            expired_keys = [k for k, t in self._history.items() if (now - t) > (self.window_seconds * 2.0)]
            for k in expired_keys:
                del self._history[k]

    def clear(self) -> None:
        with self._lock:
            self._history.clear()

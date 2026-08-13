import uuid
import time
import threading
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from movement.utils.logger import movement_logger


class JourneyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    UNREGISTERED_EXIT = "UNREGISTERED_EXIT"


class Journey(BaseModel):
    """
    In-memory person journey entity model tracking a person session from ENTRY to EXIT.
    """
    journey_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    camera_id: str = Field(..., description="Camera ID producing the initial entry")
    track_id: str = Field(..., description="Track ID associated with the entry")
    identity_id: str = Field(default="UNKNOWN", description="Matched biometric identity or 'UNKNOWN'")
    identity_status: str = Field(default="UNKNOWN")
    entry_gate_id: str = Field(..., description="Gate ID where entry occurred")
    entry_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    exit_gate_id: Optional[str] = Field(default=None)
    exit_timestamp: Optional[str] = Field(default=None)
    dwell_time: Optional[float] = Field(default=None, description="Dwell time in seconds (exit_time - entry_time)")
    status: JourneyStatus = Field(default=JourneyStatus.ACTIVE)
    last_seen_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    events: List[Dict[str, Any]] = Field(default_factory=list)

    def complete_journey(self, exit_gate_id: str, exit_iso_timestamp: str, dwell_seconds: float) -> None:
        self.exit_gate_id = exit_gate_id
        self.exit_timestamp = exit_iso_timestamp
        self.dwell_time = round(max(0.0, dwell_seconds), 2)
        self.status = JourneyStatus.COMPLETED
        self.last_seen_timestamp = exit_iso_timestamp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "journey_id": self.journey_id,
            "camera_id": self.camera_id,
            "track_id": self.track_id,
            "identity_id": self.identity_id,
            "identity_status": self.identity_status,
            "entry_gate_id": self.entry_gate_id,
            "entry_timestamp": self.entry_timestamp,
            "exit_gate_id": self.exit_gate_id,
            "exit_timestamp": self.exit_timestamp,
            "dwell_time": self.dwell_time,
            "status": self.status.value if isinstance(self.status, JourneyStatus) else str(self.status),
            "last_seen_timestamp": self.last_seen_timestamp,
            "events_count": len(self.events),
        }


class JourneyTracker:
    """
    Thread-safe In-Memory Active Journey Tracker.
    - Known identities (identity_id != 'UNKNOWN') correlate across cameras/gates.
    - Unknown identities are strictly scoped by camera_id + ':' + track_id.
    - Enforces multiple separate visits produce distinct journey_ids.
    - Handles exit without active journey safely (no fake entry/journey created).
    """

    def __init__(self):
        self._active_journeys: Dict[str, Journey] = {}
        self._completed_journeys: List[Journey] = []
        self._lock = threading.Lock()

    def _make_key(self, camera_id: str, track_id: str, identity_id: str) -> str:
        if identity_id and identity_id != "UNKNOWN":
            return f"identity:{identity_id}"
        return f"track:{camera_id}:{track_id}"

    def start_journey(
        self,
        camera_id: str,
        track_id: str,
        gate_id: str,
        identity_id: str = "UNKNOWN",
        identity_status: str = "UNKNOWN",
        timestamp: Optional[str] = None,
        event_payload: Optional[Dict[str, Any]] = None
    ) -> Journey:
        """
        Start a new active journey upon verified ENTRY.
        If an active journey already exists, returns existing (prevents duplicate journey creation).
        """
        key = self._make_key(camera_id, track_id, identity_id)
        iso_time = timestamp or datetime.now(timezone.utc).isoformat()

        with self._lock:
            if key in self._active_journeys:
                journey = self._active_journeys[key]
                if event_payload:
                    journey.events.append(event_payload)
                movement_logger.info(
                    f"Duplicate ENTRY for active journey {journey.journey_id} (key={key}). Appended event.",
                    extra={"journey_id": journey.journey_id, "camera_id": camera_id, "track_id": track_id}
                )
                return journey

            journey = Journey(
                camera_id=camera_id,
                track_id=track_id,
                identity_id=identity_id,
                identity_status=identity_status,
                entry_gate_id=gate_id,
                entry_timestamp=iso_time,
                last_seen_timestamp=iso_time,
                status=JourneyStatus.ACTIVE
            )
            if event_payload:
                journey.events.append(event_payload)

            self._active_journeys[key] = journey

        movement_logger.info(
            f"Started new active journey {journey.journey_id} for {identity_id} (gate {gate_id})",
            extra={"journey_id": journey.journey_id, "identity_id": identity_id, "camera_id": camera_id}
        )
        return journey

    def complete_journey(
        self,
        camera_id: str,
        track_id: str,
        gate_id: str,
        identity_id: str = "UNKNOWN",
        timestamp: Optional[str] = None,
        event_payload: Optional[Dict[str, Any]] = None
    ) -> Optional[Journey]:
        """
        Complete an active journey upon verified EXIT.
        Calculates dwell time, marks COMPLETED, removes from active set, and adds to completed history.
        Returns None if no active journey exists (handled safely without fabricating fake entry).
        """
        key = self._make_key(camera_id, track_id, identity_id)
        iso_time = timestamp or datetime.now(timezone.utc).isoformat()

        with self._lock:
            if key not in self._active_journeys:
                movement_logger.warning(
                    f"EXIT event received for key '{key}' with no active journey. Handled safely (dwell_time=None).",
                    extra={"camera_id": camera_id, "track_id": track_id, "identity_id": identity_id}
                )
                return None

            journey = self._active_journeys.pop(key)

            # Calculate dwell time in seconds
            try:
                t_entry = datetime.fromisoformat(journey.entry_timestamp.replace("Z", "+00:00")).timestamp()
                t_exit = datetime.fromisoformat(iso_time.replace("Z", "+00:00")).timestamp()
                dwell_sec = max(0.0, t_exit - t_entry)
            except Exception:
                dwell_sec = 0.0

            journey.complete_journey(exit_gate_id=gate_id, exit_iso_timestamp=iso_time, dwell_seconds=dwell_sec)
            if event_payload:
                journey.events.append(event_payload)

            self._completed_journeys.append(journey)

        movement_logger.info(
            f"Completed journey {journey.journey_id} for {identity_id}. Dwell time = {journey.dwell_time}s",
            extra={"journey_id": journey.journey_id, "dwell_time": journey.dwell_time, "identity_id": identity_id}
        )
        return journey

    def get_active_journey(self, camera_id: str, track_id: str, identity_id: str = "UNKNOWN") -> Optional[Journey]:
        key = self._make_key(camera_id, track_id, identity_id)
        with self._lock:
            return self._active_journeys.get(key)

    def get_active_journeys_count(self) -> int:
        with self._lock:
            return len(self._active_journeys)

    def list_active_journeys(self) -> List[Journey]:
        with self._lock:
            return list(self._active_journeys.values())

    def list_completed_journeys(self) -> List[Journey]:
        with self._lock:
            return list(self._completed_journeys)

    def clear(self) -> None:
        with self._lock:
            self._active_journeys.clear()
            self._completed_journeys.clear()

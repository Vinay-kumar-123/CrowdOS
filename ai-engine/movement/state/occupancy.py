import threading
from datetime import datetime, timezone
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from movement.utils.logger import movement_logger


class OccupancyState(BaseModel):
    """
    In-memory Occupancy State summary payload.
    Exposes venue-level, camera-level, and gate-level active inside counts.
    """
    venue_id: str = Field(default="default_venue")
    current_occupancy: int = Field(default=0, description="Active venue inside count (entries - exits, min 0)")
    total_entries: int = Field(default=0)
    total_exits: int = Field(default=0)
    gate_occupancy: Dict[str, int] = Field(default_factory=dict, description="Active inside per gate_id")
    camera_occupancy: Dict[str, int] = Field(default_factory=dict, description="Active inside per camera_id")
    active_journeys_count: int = Field(default=0)
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "venue_id": self.venue_id,
            "current_occupancy": self.current_occupancy,
            "total_entries": self.total_entries,
            "total_exits": self.total_exits,
            "gate_occupancy": dict(self.gate_occupancy),
            "camera_occupancy": dict(self.camera_occupancy),
            "active_journeys_count": self.active_journeys_count,
            "last_updated": self.last_updated,
        }


class OccupancyTracker:
    """
    Thread-safe In-Memory Occupancy Tracker.
    Maintains venue-level, camera-level, and gate-level occupancy counts.
    Enforces non-negative bounds: max(0, entries - exits).
    """

    def __init__(self, venue_id: str = "default_venue"):
        self.venue_id = venue_id
        self._total_entries = 0
        self._total_exits = 0
        self._current_occupancy = 0
        self._gate_occupancy: Dict[str, int] = {}
        self._camera_occupancy: Dict[str, int] = {}
        self._lock = threading.Lock()

    def record_entry(self, camera_id: str, gate_id: str) -> None:
        """
        Record a verified ENTRY event. Increments occupancy counts.
        """
        with self._lock:
            self._total_entries += 1
            self._current_occupancy += 1
            self._gate_occupancy[gate_id] = self._gate_occupancy.get(gate_id, 0) + 1
            self._camera_occupancy[camera_id] = self._camera_occupancy.get(camera_id, 0) + 1

        movement_logger.info(
            f"Occupancy ENTRY recorded on gate {gate_id} (camera {camera_id}). Venue occupancy = {self._current_occupancy}",
            extra={"camera_id": camera_id, "gate_id": gate_id, "current_occupancy": self._current_occupancy}
        )

    def record_exit(self, camera_id: str, gate_id: str) -> None:
        """
        Record a verified EXIT event. Decrements occupancy counts safely (min 0).
        """
        with self._lock:
            self._total_exits += 1
            # Prevent negative venue occupancy
            if self._current_occupancy > 0:
                self._current_occupancy -= 1
            else:
                movement_logger.warning(
                    f"Occupancy EXIT on gate {gate_id} occurred when venue occupancy was 0. Bound to 0.",
                    extra={"camera_id": camera_id, "gate_id": gate_id}
                )

            # Prevent negative gate occupancy
            if self._gate_occupancy.get(gate_id, 0) > 0:
                self._gate_occupancy[gate_id] -= 1

            # Prevent negative camera occupancy
            if self._camera_occupancy.get(camera_id, 0) > 0:
                self._camera_occupancy[camera_id] -= 1

        movement_logger.info(
            f"Occupancy EXIT recorded on gate {gate_id} (camera {camera_id}). Venue occupancy = {self._current_occupancy}",
            extra={"camera_id": camera_id, "gate_id": gate_id, "current_occupancy": self._current_occupancy}
        )

    def get_state(self, active_journeys_count: int = 0) -> OccupancyState:
        with self._lock:
            return OccupancyState(
                venue_id=self.venue_id,
                current_occupancy=self._current_occupancy,
                total_entries=self._total_entries,
                total_exits=self._total_exits,
                gate_occupancy=dict(self._gate_occupancy),
                camera_occupancy=dict(self._camera_occupancy),
                active_journeys_count=active_journeys_count,
                last_updated=datetime.now(timezone.utc).isoformat()
            )

    def reset(self) -> None:
        with self._lock:
            self._total_entries = 0
            self._total_exits = 0
            self._current_occupancy = 0
            self._gate_occupancy.clear()
            self._camera_occupancy.clear()

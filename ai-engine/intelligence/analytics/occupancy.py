"""
Occupancy Analytics Module.
CRITICAL ARCHITECTURE RULE: Sprint 6 is the authoritative physical occupancy source.
Sprint 7 MUST NOT create a competing physical occupancy counter.
This module consumes Sprint 6 OccupancyState payloads and computes gate distributions,
busiest gates, least active gates, and venue occupancy summaries.
"""
import threading
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from movement.state.occupancy import OccupancyState


class OccupancyAnalyticsSummary(BaseModel):
    """
    Summary payload generated from authoritative Sprint 6 OccupancyState.
    """
    venue_id: str = Field(default="default_venue")
    current_occupancy: int = Field(default=0)
    total_entries: int = Field(default=0)
    total_exits: int = Field(default=0)
    gate_occupancy: Dict[str, int] = Field(default_factory=dict)
    camera_occupancy: Dict[str, int] = Field(default_factory=dict)
    busiest_gate: Optional[str] = Field(default=None, description="Gate ID with highest occupancy/activity")
    least_active_gate: Optional[str] = Field(default=None, description="Gate ID with lowest occupancy/activity")
    last_updated: str = Field(default="")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class OccupancyAnalytics:
    """
    Thread-safe Occupancy Analytics Engine.
    Consumes authoritative Sprint 6 OccupancyState objects.
    """

    def __init__(self, venue_id: str = "default_venue"):
        self.venue_id = venue_id
        self._last_state: Optional[OccupancyState] = None
        self._gate_activity_counter: Dict[str, int] = {}
        self._lock = threading.Lock()

    def consume_occupancy_state(self, state: OccupancyState) -> OccupancyAnalyticsSummary:
        """
        Ingest authoritative OccupancyState snapshot from Sprint 6.
        """
        with self._lock:
            self._last_state = state
            # Record gate activity for busiest/least active tracking
            for gate_id, occ in state.gate_occupancy.items():
                if gate_id not in self._gate_activity_counter:
                    self._gate_activity_counter[gate_id] = occ
                else:
                    self._gate_activity_counter[gate_id] = max(self._gate_activity_counter[gate_id], occ)

            return self._build_summary_unlocked()

    def get_summary(self) -> OccupancyAnalyticsSummary:
        with self._lock:
            if not self._last_state:
                return OccupancyAnalyticsSummary(venue_id=self.venue_id)
            return self._build_summary_unlocked()

    def _build_summary_unlocked(self) -> OccupancyAnalyticsSummary:
        st = self._last_state
        if not st:
            return OccupancyAnalyticsSummary(venue_id=self.venue_id)

        gate_occ = dict(st.gate_occupancy)
        busiest = None
        least_active = None

        if gate_occ:
            sorted_gates = sorted(gate_occ.items(), key=lambda x: x[1], reverse=True)
            busiest = sorted_gates[0][0]
            least_active = sorted_gates[-1][0]

        return OccupancyAnalyticsSummary(
            venue_id=st.venue_id,
            current_occupancy=st.current_occupancy,
            total_entries=st.total_entries,
            total_exits=st.total_exits,
            gate_occupancy=gate_occ,
            camera_occupancy=dict(st.camera_occupancy),
            busiest_gate=busiest,
            least_active_gate=least_active,
            last_updated=st.last_updated
        )

    def reset(self) -> None:
        with self._lock:
            self._last_state = None
            self._gate_activity_counter.clear()

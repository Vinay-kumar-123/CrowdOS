"""
Sprint 7 Intelligence Engine Test Fixtures and Synthetic Generators.
Uses Sprint 6 event models (EntryEvent, ExitEvent, MovementEvent, OccupancyState, Journey).
"""
import uuid
import pytest
from datetime import datetime, timezone
from movement.events.schema import EntryEvent, ExitEvent, MovementEvent, MovementEventType
from movement.state.occupancy import OccupancyState
from movement.state.journey import Journey, JourneyStatus
from intelligence.engine.intelligence_engine import EventIntelligenceEngine


def make_entry_event(
    camera_id: str = "cam_01",
    gate_id: str = "gate_main",
    track_id: str = "1",
    identity_id: str = "UNKNOWN",
    timestamp: str = None
) -> EntryEvent:
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    return EntryEvent(
        camera_id=camera_id,
        gate_id=gate_id,
        entry_gate_id=gate_id,
        track_id=track_id,
        detection_id=str(uuid.uuid4()),
        identity_id=identity_id,
        timestamp=ts,
        direction="ENTRY"
    )


def make_exit_event(
    camera_id: str = "cam_01",
    gate_id: str = "gate_main",
    track_id: str = "1",
    identity_id: str = "UNKNOWN",
    dwell_time: float = 120.0,
    timestamp: str = None
) -> ExitEvent:
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    return ExitEvent(
        camera_id=camera_id,
        gate_id=gate_id,
        exit_gate_id=gate_id,
        track_id=track_id,
        detection_id=str(uuid.uuid4()),
        identity_id=identity_id,
        timestamp=ts,
        direction="EXIT",
        dwell_time=dwell_time
    )


def make_occupancy_state(
    current_occupancy: int = 10,
    total_entries: int = 20,
    total_exits: int = 10,
    gate_occupancy: dict = None,
    venue_id: str = "default_venue"
) -> OccupancyState:
    g_occ = gate_occupancy or {"gate_main": current_occupancy}
    return OccupancyState(
        venue_id=venue_id,
        current_occupancy=current_occupancy,
        total_entries=total_entries,
        total_exits=total_exits,
        gate_occupancy=g_occ,
        camera_occupancy={"cam_01": current_occupancy}
    )


@pytest.fixture
def engine():
    return EventIntelligenceEngine(venue_id="test_venue")

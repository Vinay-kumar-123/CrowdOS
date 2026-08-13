"""
End-to-End Integration & Regression Tests for Sprint 7.
"""
import pytest
from movement.state.occupancy import OccupancyState
from movement.state.journey import Journey, JourneyStatus
from intelligence.engine.intelligence_engine import EventIntelligenceEngine
from .conftest import make_entry_event, make_exit_event


def test_full_pipeline_end_to_end_integration():
    engine = EventIntelligenceEngine(venue_id="venue_e2e")
    session = engine.session_manager.create_session(venue_id="venue_e2e")
    engine.session_manager.start_session(session.session_id)

    # 1. Ingest Entries across gates
    for i in range(10):
        engine.process_event(make_entry_event(camera_id="cam_01", gate_id="gate_north", track_id=f"n_{i}"))
    for i in range(5):
        engine.process_event(make_entry_event(camera_id="cam_02", gate_id="gate_south", track_id=f"s_{i}"))

    # 2. Ingest Sprint 6 OccupancyState update
    occ_state = OccupancyState(
        venue_id="venue_e2e",
        current_occupancy=15,
        total_entries=15,
        total_exits=0,
        gate_occupancy={"gate_north": 10, "gate_south": 5}
    )
    summary_occ = engine.process_occupancy_state(occ_state)
    assert summary_occ.current_occupancy == 15
    assert summary_occ.busiest_gate == "gate_north"

    # 3. Ingest Exits and Journeys
    for i in range(3):
        engine.process_event(make_exit_event(camera_id="cam_01", gate_id="gate_north", track_id=f"n_{i}", dwell_time=180.0))

    journey = Journey(
        camera_id="cam_01",
        track_id="n_0",
        entry_gate_id="gate_north",
        exit_gate_id="gate_north",
        dwell_time=180.0,
        status=JourneyStatus.COMPLETED
    )
    engine.process_journey(journey)

    # 4. Inspect current intelligence
    intel = engine.get_current_intelligence()
    assert intel["flow"]["cumulative_entries"] == 15
    assert intel["flow"]["cumulative_exits"] == 3
    assert intel["dwell"]["average_dwell"] == 180.0

    # 5. Stop session and verify summary
    summary = engine.stop_session(session.session_id)
    assert summary is not None
    assert summary.total_entries == 15
    assert summary.total_exits == 3
    assert summary.peak_occupancy == 15
    assert summary.busiest_gate == "gate_north"

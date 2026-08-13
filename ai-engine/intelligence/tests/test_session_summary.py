"""
Tests for SessionSummary Generation and Immutability.
"""
import pytest
from movement.state.occupancy import OccupancyState
from intelligence.engine.intelligence_engine import EventIntelligenceEngine
from .conftest import make_entry_event, make_exit_event


def test_session_summary_totals_and_peaks(engine):
    session = engine.session_manager.create_session()
    engine.session_manager.start_session(session.session_id)

    # Simulate 5 entries, 2 exits
    for i in range(5):
        engine.process_event(make_entry_event(gate_id="gate_A", track_id=str(i+1)))
    for i in range(2):
        engine.process_event(make_exit_event(gate_id="gate_A", track_id=str(i+1), dwell_time=100.0))

    engine.process_occupancy_state(OccupancyState(
        venue_id="test_venue", current_occupancy=3, total_entries=5, total_exits=2,
        gate_occupancy={"gate_A": 3}
    ))

    summary = engine.stop_session(session.session_id)
    assert summary is not None
    assert summary.total_entries == 5
    assert summary.total_exits == 2
    assert summary.peak_occupancy == 3
    assert summary.busiest_gate == "gate_A"
    assert summary.average_dwell == 100.0


def test_session_summary_immutability(engine):
    """Once a session is STOPPED, the summary snapshot must be frozen and immutable to subsequent events."""
    session = engine.session_manager.create_session()
    engine.session_manager.start_session(session.session_id)

    engine.process_event(make_entry_event(gate_id="gate_A", track_id="1"))
    summary1 = engine.stop_session(session.session_id)
    assert summary1.total_entries == 1

    # Ingest event after session stopped
    engine.process_event(make_entry_event(gate_id="gate_A", track_id="2"))

    # Re-fetch summary -> must remain unchanged (1 total entry)
    summary2 = engine.stop_session(session.session_id)
    assert summary2.total_entries == 1
    assert summary2.session_id == summary1.session_id

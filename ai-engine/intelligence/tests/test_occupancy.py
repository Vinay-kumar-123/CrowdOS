"""
Tests for Occupancy Analytics (verifying Sprint 6 OccupancyState is authoritative source of truth).
"""
import pytest
from intelligence.analytics.occupancy import OccupancyAnalytics
from .conftest import make_occupancy_state


def test_consume_sprint6_occupancy_state():
    occ_analytics = OccupancyAnalytics(venue_id="venue_01")
    state = make_occupancy_state(
        current_occupancy=42,
        total_entries=100,
        total_exits=58,
        gate_occupancy={"gate_A": 30, "gate_B": 12}
    )

    summary = occ_analytics.consume_occupancy_state(state)
    assert summary.current_occupancy == 42
    assert summary.total_entries == 100
    assert summary.total_exits == 58
    assert summary.gate_occupancy["gate_A"] == 30
    assert summary.busiest_gate == "gate_A"
    assert summary.least_active_gate == "gate_B"


def test_occupancy_analytics_no_independent_counting():
    """
    OccupancyAnalytics must NOT independently count entries/exits from zero;
    it strictly mirrors Sprint 6 OccupancyState.
    """
    occ_analytics = OccupancyAnalytics(venue_id="venue_01")
    # Empty initial summary
    summary0 = occ_analytics.get_summary()
    assert summary0.current_occupancy == 0

    # Ingest Sprint 6 state
    state = make_occupancy_state(current_occupancy=150)
    summary1 = occ_analytics.consume_occupancy_state(state)
    assert summary1.current_occupancy == 150

"""
Tests for Arbitrary Multi-Gate Scaling & Isolation (1, 3, 10, 100+ gates).
"""
import pytest
from intelligence.analytics.flow import FlowAnalytics


def test_single_gate_flow():
    flow = FlowAnalytics()
    flow.record_event("ENTRY", "gate_1")
    res = flow.get_gate_flow("gate_1")
    assert res.cumulative_entries == 1


def test_three_gates_flow():
    flow = FlowAnalytics()
    for i in range(3):
        gid = f"gate_{i+1}"
        for _ in range((i + 1) * 10):
            flow.record_event("ENTRY", gid)

    assert flow.get_gate_flow("gate_1").cumulative_entries == 10
    assert flow.get_gate_flow("gate_2").cumulative_entries == 20
    assert flow.get_gate_flow("gate_3").cumulative_entries == 30

    venue_flow = flow.get_venue_flow()
    assert venue_flow.cumulative_entries == 60


def test_large_scale_100_gates_flow_isolation():
    """Verify system handles 100+ gates without architectural changes or cross-contamination."""
    flow = FlowAnalytics()

    for i in range(100):
        gid = f"gate_{i+1}"
        flow.record_event("ENTRY", gid)

    all_flows = flow.get_all_gate_flows()
    assert len(all_flows) == 100

    for i in range(100):
        gid = f"gate_{i+1}"
        assert all_flows[gid].cumulative_entries == 1

    assert flow.get_venue_flow().cumulative_entries == 100

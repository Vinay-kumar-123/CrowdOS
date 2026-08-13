"""
Tests for Flow Analytics (rates, net flow, windowing, out-of-order timestamps, duplicates).
"""
import pytest
import time
from datetime import datetime, timezone, timedelta
from intelligence.analytics.flow import FlowAnalytics
from .conftest import make_entry_event, make_exit_event


def test_flow_analytics_cumulative_counts():
    flow = FlowAnalytics(venue_id="venue_01")
    flow.record_event("ENTRY", "gate_A")
    flow.record_event("ENTRY", "gate_A")
    flow.record_event("EXIT", "gate_A")

    metrics = flow.get_venue_flow()
    assert metrics.cumulative_entries == 2
    assert metrics.cumulative_exits == 1
    assert metrics.cumulative_net_flow == 1


def test_flow_rate_calculation():
    """
    25 entries in 5 minutes -> 5.0 persons/minute rate.
    """
    flow = FlowAnalytics(venue_id="venue_01")
    now_epoch = time.time()

    for i in range(25):
        # Evenly spread over 5 minutes (300s)
        ts_epoch = now_epoch - (i * 10)
        ts_iso = datetime.fromtimestamp(ts_epoch, timezone.utc).isoformat()
        flow.record_event("ENTRY", "gate_A", timestamp=ts_iso)

    metrics = flow.get_venue_flow(current_time=now_epoch)
    # 5m rate = 25 / 5 = 5.0 persons/min
    assert abs(metrics.entry_rate_5m - 5.0) < 0.2


def test_net_flow_rate():
    flow = FlowAnalytics()
    now_epoch = time.time()

    # 10 entries, 4 exits in 1 minute window
    for _ in range(10):
        flow.record_event("ENTRY", "gate_A", timestamp=datetime.fromtimestamp(now_epoch, timezone.utc).isoformat())
    for _ in range(4):
        flow.record_event("EXIT", "gate_A", timestamp=datetime.fromtimestamp(now_epoch, timezone.utc).isoformat())

    metrics = flow.get_venue_flow(current_time=now_epoch)
    assert metrics.entry_rate_1m == 10.0
    assert metrics.exit_rate_1m == 4.0
    assert metrics.net_flow_rate_1m == 6.0


def test_gate_level_flow_isolation():
    flow = FlowAnalytics()
    flow.record_event("ENTRY", "gate_A")
    flow.record_event("ENTRY", "gate_B")

    flow_a = flow.get_gate_flow("gate_A")
    flow_b = flow.get_gate_flow("gate_B")

    assert flow_a.cumulative_entries == 1
    assert flow_b.cumulative_entries == 1


def test_duplicate_event_suppression():
    """Events with duplicate event_id must not double count."""
    flow = FlowAnalytics()
    flow.record_event("ENTRY", "gate_A", event_id="evt_100")
    # Duplicate call
    processed = flow.record_event("ENTRY", "gate_A", event_id="evt_100")

    assert not processed
    metrics = flow.get_venue_flow()
    assert metrics.cumulative_entries == 1


def test_out_of_order_timestamps():
    """Out-of-order events are placed into correct time windows based on timestamp."""
    flow = FlowAnalytics()
    now_epoch = time.time()

    # Arrive out of order: T0 (now), T0-200s, T0-100s
    t0_iso = datetime.fromtimestamp(now_epoch, timezone.utc).isoformat()
    t1_iso = datetime.fromtimestamp(now_epoch - 200, timezone.utc).isoformat()
    t2_iso = datetime.fromtimestamp(now_epoch - 100, timezone.utc).isoformat()

    flow.record_event("ENTRY", "gate_A", timestamp=t0_iso)
    flow.record_event("ENTRY", "gate_A", timestamp=t1_iso)
    flow.record_event("ENTRY", "gate_A", timestamp=t2_iso)

    metrics = flow.get_venue_flow(current_time=now_epoch)
    assert metrics.cumulative_entries == 3
    # All 3 within 5m window
    assert metrics.entry_rate_5m > 0.0

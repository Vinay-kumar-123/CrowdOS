"""
Tests for Alert Deduplication (session-aware scope, venue vs gate isolation).
"""
import pytest
from intelligence.alerts.deduplicator import AlertDeduplicator
from intelligence.alerts.schema import AlertEvent


def test_session_aware_scope_key():
    dedup = AlertDeduplicator()
    k1 = dedup.make_key("sess_A", "venue_1", "gate_1", "CONGESTION")
    k2 = dedup.make_key("sess_B", "venue_1", "gate_1", "CONGESTION")
    k_global = dedup.make_key("sess_A", "venue_1", None, "CONGESTION")

    assert k1 != k2
    assert k1 != k_global
    assert k_global == "sess_A:venue_1:GLOBAL:CONGESTION"


def test_gate_isolation_deduplication():
    """Gate A congestion and Gate B congestion must remain separate active alerts."""
    dedup = AlertDeduplicator()

    a1 = AlertEvent(session_id="s1", venue_id="v1", gate_id="gate_A", type="CONGESTION")
    a2 = AlertEvent(session_id="s1", venue_id="v1", gate_id="gate_B", type="CONGESTION")

    dedup.register_active_alert(a1)
    dedup.register_active_alert(a2)

    active_a = dedup.get_active_alert_id("s1", "v1", "gate_A", "CONGESTION")
    active_b = dedup.get_active_alert_id("s1", "v1", "gate_B", "CONGESTION")

    assert active_a == a1.alert_id
    assert active_b == a2.alert_id
    assert active_a != active_b

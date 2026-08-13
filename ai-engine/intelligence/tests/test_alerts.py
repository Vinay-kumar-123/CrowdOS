"""
Tests for Alert Engine Lifecycle (Create, Active update, Resolve, Recurrence).
"""
import pytest
from intelligence.alerts.manager import AlertManager
from intelligence.alerts.schema import AlertStatus, AlertSeverity


def test_alert_creation_and_active_update():
    mgr = AlertManager()

    # Process anomaly 1 -> Alert created
    alert1, created1 = mgr.process_anomaly(
        session_id="sess_1",
        venue_id="venue_1",
        alert_type="ENTRY_SURGE",
        severity="HIGH"
    )

    assert created1
    assert alert1.status == AlertStatus.ACTIVE
    assert alert1.type == "ENTRY_SURGE"
    assert len(mgr.get_active_alerts()) == 1

    # Process same anomaly again -> Alert updated (last_seen updated, no duplicate created)
    alert2, created2 = mgr.process_anomaly(
        session_id="sess_1",
        venue_id="venue_1",
        alert_type="ENTRY_SURGE",
        severity="HIGH"
    )

    assert not created2
    assert alert2.alert_id == alert1.alert_id
    assert len(mgr.get_active_alerts()) == 1


def test_alert_resolution():
    mgr = AlertManager()
    mgr.process_anomaly(session_id="sess_1", venue_id="venue_1", alert_type="ENTRY_SURGE")

    assert len(mgr.get_active_alerts()) == 1

    # Resolve alert
    resolved = mgr.resolve_alert(session_id="sess_1", venue_id="venue_1", alert_type="ENTRY_SURGE")
    assert resolved is not None
    assert resolved.status == AlertStatus.RESOLVED
    assert len(mgr.get_active_alerts()) == 0
    assert len(mgr.get_resolved_alerts()) == 1


def test_alert_recurrence_after_resolution():
    """An alert resolved and later triggered again must create a new AlertEvent instance."""
    mgr = AlertManager()

    # 1. Create & Resolve
    alert1, _ = mgr.process_anomaly(session_id="sess_1", venue_id="venue_1", alert_type="ENTRY_SURGE")
    mgr.resolve_alert(session_id="sess_1", venue_id="venue_1", alert_type="ENTRY_SURGE")

    # 2. Trigger again after resolution
    alert2, created2 = mgr.process_anomaly(session_id="sess_1", venue_id="venue_1", alert_type="ENTRY_SURGE")

    assert created2
    assert alert2.alert_id != alert1.alert_id
    assert len(mgr.get_active_alerts()) == 1

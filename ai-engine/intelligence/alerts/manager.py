"""
Thread-safe Alert Manager.
Manages AlertEvent lifecycles (creation, active update, resolution).
Uses AlertDeduplicator to guarantee thread-safe session-aware alert deduplication.
"""
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional
from intelligence.alerts.schema import AlertEvent, AlertSeverity, AlertStatus
from intelligence.alerts.deduplicator import AlertDeduplicator
from intelligence.utils.logger import intelligence_logger


class AlertManager:
    """
    Thread-safe Alert Lifecycle Manager.
    """

    def __init__(self):
        self._active_alerts: Dict[str, AlertEvent] = {}
        self._resolved_alerts: List[AlertEvent] = []
        self._deduplicator = AlertDeduplicator()
        self._lock = threading.Lock()

    def process_anomaly(
        self,
        session_id: str,
        venue_id: str,
        alert_type: str,
        severity: str = "MEDIUM",
        gate_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        timestamp: Optional[str] = None
    ) -> Tuple_Alert_or_Existing:
        """
        Ingest an anomaly. If active alert exists for (session_id, venue_id, gate_id, alert_type),
        updates last_seen. Otherwise creates a new active AlertEvent.
        """
        now_iso = timestamp or datetime.now(timezone.utc).isoformat()
        severity_enum = AlertSeverity[severity.upper()] if hasattr(AlertSeverity, severity.upper()) else AlertSeverity.MEDIUM

        active_id = self._deduplicator.get_active_alert_id(session_id, venue_id, gate_id, alert_type)

        with self._lock:
            if active_id and active_id in self._active_alerts:
                alert = self._active_alerts[active_id]
                alert.update_last_seen(now_iso)
                if metadata:
                    alert.metadata.update(metadata)
                return alert, False  # Existing updated

            # Create new AlertEvent
            alert = AlertEvent(
                session_id=session_id,
                venue_id=venue_id,
                gate_id=gate_id,
                type=alert_type,
                severity=severity_enum,
                status=AlertStatus.ACTIVE,
                created_at=now_iso,
                last_seen=now_iso,
                metadata=metadata or {}
            )
            self._active_alerts[alert.alert_id] = alert
            self._deduplicator.register_active_alert(alert)

        intelligence_logger.info(
            f"Created new active alert {alert.alert_id} ({alert_type}) for venue {venue_id}",
            extra={"alert_id": alert.alert_id, "session_id": session_id, "alert_type": alert_type}
        )
        return alert, True  # Newly created

    def resolve_alert(
        self,
        session_id: str,
        venue_id: str,
        alert_type: str,
        gate_id: Optional[str] = None,
        timestamp: Optional[str] = None
    ) -> Optional[AlertEvent]:
        """
        Resolve an active alert when anomaly conditions subside.
        """
        now_iso = timestamp or datetime.now(timezone.utc).isoformat()
        active_id = self._deduplicator.get_active_alert_id(session_id, venue_id, gate_id, alert_type)
        if not active_id:
            return None

        with self._lock:
            alert = self._active_alerts.pop(active_id, None)
            if alert:
                alert.mark_resolved(now_iso)
                self._resolved_alerts.append(alert)
                self._deduplicator.clear_active_alert(session_id, venue_id, gate_id, alert_type)

        if alert:
            intelligence_logger.info(
                f"Resolved alert {alert.alert_id} ({alert_type}) for venue {venue_id}",
                extra={"alert_id": alert.alert_id, "session_id": session_id}
            )
        return alert

    def get_active_alerts(self) -> List[AlertEvent]:
        with self._lock:
            return list(self._active_alerts.values())

    def get_resolved_alerts(self) -> List[AlertEvent]:
        with self._lock:
            return list(self._resolved_alerts)

    def get_all_alerts(self) -> List[AlertEvent]:
        with self._lock:
            return list(self._active_alerts.values()) + list(self._resolved_alerts)

    def reset(self) -> None:
        with self._lock:
            self._active_alerts.clear()
            self._resolved_alerts.clear()
            self._deduplicator.clear()

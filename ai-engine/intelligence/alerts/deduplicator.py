"""
Thread-safe Session-Aware Alert Deduplicator.
Scope key: session_id:venue_id:gate_id_or_GLOBAL:alert_type.
Prevents duplicate active alerts while permitting new instances after resolution.
"""
import threading
from typing import Dict, Optional
from intelligence.alerts.schema import AlertEvent, AlertStatus


class AlertDeduplicator:
    """
    Session-aware Alert Deduplicator.
    """

    def __init__(self):
        # Maps scope_key -> active_alert_id
        self._active_keys: Dict[str, str] = {}
        self._lock = threading.Lock()

    def make_key(self, session_id: str, venue_id: str, gate_id: Optional[str], alert_type: str) -> str:
        gid_str = gate_id if gate_id else "GLOBAL"
        return f"{session_id}:{venue_id}:{gid_str}:{alert_type}"

    def get_active_alert_id(
        self,
        session_id: str,
        venue_id: str,
        gate_id: Optional[str],
        alert_type: str
    ) -> Optional[str]:
        key = self.make_key(session_id, venue_id, gate_id, alert_type)
        with self._lock:
            return self._active_keys.get(key)

    def register_active_alert(self, alert: AlertEvent) -> str:
        key = self.make_key(alert.session_id, alert.venue_id, alert.gate_id, alert.type)
        with self._lock:
            self._active_keys[key] = alert.alert_id
            return key

    def clear_active_alert(self, session_id: str, venue_id: str, gate_id: Optional[str], alert_type: str) -> bool:
        key = self.make_key(session_id, venue_id, gate_id, alert_type)
        with self._lock:
            if key in self._active_keys:
                del self._active_keys[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._active_keys.clear()

"""
Thread-safe Metrics Tracker for CrowdOS Event Intelligence Engine.
Zero biometric vectors or sensitive payload fields exposed.
"""
import threading
from typing import Dict, Any


class IntelligenceMetricsTracker:
    """
    In-process performance and operation metrics counter.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._events_processed = 0
        self._events_rejected = 0
        self._entries_processed = 0
        self._exits_processed = 0
        self._alerts_created = 0
        self._alerts_resolved = 0
        self._duplicate_events = 0
        self._processing_errors = 0
        self._total_latency_ms = 0.0

    def record_event_processed(self, is_entry: bool = False, is_exit: bool = False, latency_ms: float = 0.0) -> None:
        with self._lock:
            self._events_processed += 1
            if is_entry:
                self._entries_processed += 1
            elif is_exit:
                self._exits_processed += 1
            self._total_latency_ms += max(0.0, latency_ms)

    def record_event_rejected(self) -> None:
        with self._lock:
            self._events_rejected += 1

    def record_duplicate_event(self) -> None:
        with self._lock:
            self._duplicate_events += 1

    def record_alert_created(self) -> None:
        with self._lock:
            self._alerts_created += 1

    def record_alert_resolved(self) -> None:
        with self._lock:
            self._alerts_resolved += 1

    def record_error(self) -> None:
        with self._lock:
            self._processing_errors += 1

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            avg_lat = (self._total_latency_ms / self._events_processed) if self._events_processed > 0 else 0.0
            return {
                "events_processed": self._events_processed,
                "events_rejected": self._events_rejected,
                "entries_processed": self._entries_processed,
                "exits_processed": self._exits_processed,
                "alerts_created": self._alerts_created,
                "alerts_resolved": self._alerts_resolved,
                "duplicate_events": self._duplicate_events,
                "processing_errors": self._processing_errors,
                "avg_processing_latency_ms": round(avg_lat, 3)
            }

    def reset(self) -> None:
        with self._lock:
            self._events_processed = 0
            self._events_rejected = 0
            self._entries_processed = 0
            self._exits_processed = 0
            self._alerts_created = 0
            self._alerts_resolved = 0
            self._duplicate_events = 0
            self._processing_errors = 0
            self._total_latency_ms = 0.0

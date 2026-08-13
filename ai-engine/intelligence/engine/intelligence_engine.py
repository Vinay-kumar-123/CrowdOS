"""
EventIntelligenceEngine Orchestrator.
Consumes Sprint 6 MovementEvent/EntryEvent/ExitEvent, Journey, and OccupancyState objects.
Computes flow rates, crowd density, congestion levels, anomalies, alerts, and immutable session summaries.
Thread-safe and purely in-memory.
"""
import time
import threading
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from movement.events.schema import MovementEvent, EntryEvent, ExitEvent, MovementEventType
from movement.state.occupancy import OccupancyState
from movement.state.journey import Journey, JourneyStatus

from intelligence.config.settings import IntelligenceSettings, default_intelligence_settings
from intelligence.config.thresholds import CrowdThresholdConfig, CongestionThresholdConfig
from intelligence.session.session import MonitoringSession, SessionStatus
from intelligence.session.session_manager import SessionManager
from intelligence.session.session_summary import SessionSummary
from intelligence.analytics.flow import FlowAnalytics, FlowMetrics
from intelligence.analytics.occupancy import OccupancyAnalytics, OccupancyAnalyticsSummary
from intelligence.analytics.density import DensityAnalytics, DensityState
from intelligence.analytics.dwell import DwellAnalytics, DwellMetrics
from intelligence.analytics.peak import PeakTracker, PeakMetrics
from intelligence.anomaly.detector import AnomalyDetector
from intelligence.alerts.manager import AlertManager
from intelligence.alerts.schema import AlertEvent
from intelligence.metrics.metrics import IntelligenceMetricsTracker
from intelligence.utils.logger import intelligence_logger


class EventIntelligenceEngine:
    """
    Top-level Event Intelligence & Session Management Orchestrator.
    Consumes Sprint 6 outputs directly.
    """

    def __init__(
        self,
        venue_id: str = "default_venue",
        crowd_config: Optional[CrowdThresholdConfig] = None,
        congestion_config: Optional[CongestionThresholdConfig] = None,
        settings: Optional[IntelligenceSettings] = None
    ):
        self.venue_id = venue_id
        self.settings = settings or default_intelligence_settings
        self.crowd_config = crowd_config or CrowdThresholdConfig()
        self.congestion_config = congestion_config or CongestionThresholdConfig()

        self._lock = threading.Lock()

        # Engine Subsystems
        self.session_manager = SessionManager(venue_id=venue_id)
        self.flow_analytics = FlowAnalytics(venue_id=venue_id)
        self.occupancy_analytics = OccupancyAnalytics(venue_id=venue_id)
        self.density_analytics = DensityAnalytics(
            crowd_config=self.crowd_config,
            congestion_config=self.congestion_config,
            venue_id=venue_id
        )
        self.dwell_analytics = DwellAnalytics()
        self.peak_tracker = PeakTracker(venue_id=venue_id)
        self.anomaly_detector = AnomalyDetector(
            crowd_config=self.crowd_config,
            congestion_config=self.congestion_config
        )
        self.alert_manager = AlertManager()
        self.metrics = IntelligenceMetricsTracker()

        # Storage for immutable session summaries when stopped
        self._stopped_summaries: Dict[str, SessionSummary] = {}

    def process_event(self, event: Any) -> Dict[str, Any]:
        """
        Process a Sprint 6 MovementEvent / EntryEvent / ExitEvent payload.
        Returns evaluation result dictionary.
        """
        t0 = time.perf_counter()
        if not event:
            self.metrics.record_event_rejected()
            return {"status": "rejected", "reason": "None event"}

        # Validate event payload
        try:
            event_type = getattr(event, "event_type", None)
            if hasattr(event_type, "value"):
                evt_type_str = event_type.value
            else:
                evt_type_str = str(event_type or "")

            gate_id = getattr(event, "gate_id", None) or getattr(event, "entry_gate_id", None) or getattr(event, "exit_gate_id", "default_gate")
            timestamp = getattr(event, "timestamp", None) or datetime.now(timezone.utc).isoformat()
            event_id = getattr(event, "event_id", None)

            # Record event in flow analytics
            is_entry = (evt_type_str == "ENTRY")
            is_exit = (evt_type_str == "EXIT")

            processed = self.flow_analytics.record_event(
                event_type=evt_type_str,
                gate_id=gate_id,
                timestamp=timestamp,
                event_id=event_id
            )

            if not processed:
                self.metrics.record_duplicate_event()
                return {"status": "ignored", "reason": "Duplicate event"}

            # Handle ExitEvent dwell time if available
            if is_exit and hasattr(event, "dwell_time"):
                dwell = getattr(event, "dwell_time", None)
                if dwell is not None:
                    self.dwell_analytics.record_dwell(dwell)

            # Update peaks
            venue_flow = self.flow_analytics.get_venue_flow()
            self.peak_tracker.update_entry_rate(venue_flow.entry_rate_5m, timestamp)
            self.peak_tracker.update_exit_rate(venue_flow.exit_rate_5m, timestamp)

            # Check active session ID
            active_session = self.session_manager.get_active_session()
            session_id = active_session.session_id if active_session else "global_session"

            # Evaluate anomalies & alerts
            occ_summary = self.occupancy_analytics.get_summary()
            gate_flows = self.flow_analytics.get_all_gate_flows()
            anomalies = self.anomaly_detector.evaluate_anomalies(venue_flow, occ_summary, gate_flows)

            generated_alerts = []
            for anom in anomalies:
                alert, created = self.alert_manager.process_anomaly(
                    session_id=session_id,
                    venue_id=self.venue_id,
                    alert_type=anom.anomaly_type.value,
                    severity=anom.severity,
                    gate_id=anom.gate_id,
                    metadata=anom.metadata,
                    timestamp=timestamp
                )
                if created:
                    self.metrics.record_alert_created()
                generated_alerts.append(alert.to_dict())

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self.metrics.record_event_processed(is_entry=is_entry, is_exit=is_exit, latency_ms=elapsed_ms)

            return {
                "status": "processed",
                "event_type": evt_type_str,
                "gate_id": gate_id,
                "alerts_generated": len(generated_alerts),
                "processing_time_ms": round(elapsed_ms, 3)
            }

        except Exception as e:
            intelligence_logger.error(f"Error processing event in EventIntelligenceEngine: {e}")
            self.metrics.record_error()
            return {"status": "error", "reason": str(e)}

    def process_occupancy_state(self, state: OccupancyState) -> OccupancyAnalyticsSummary:
        """
        Consume authoritative OccupancyState payload from Sprint 6.
        Updates density evaluation and peak occupancy.
        """
        if not state:
            return self.occupancy_analytics.get_summary()

        summary = self.occupancy_analytics.consume_occupancy_state(state)

        # Update peak occupancy
        self.peak_tracker.update_occupancy(state.current_occupancy, state.last_updated)

        # Evaluate density & congestion
        venue_flow = self.flow_analytics.get_venue_flow()
        density_state = self.density_analytics.evaluate(
            occupancy=state.current_occupancy,
            net_flow_rate_5m=venue_flow.net_flow_rate_5m
        )

        # Update peak congestion
        self.peak_tracker.update_congestion(density_state.congestion_level, state.last_updated)

        return summary

    def process_journey(self, journey: Journey) -> None:
        """
        Consume completed Journey payload from Sprint 6.
        Aggregates dwell time safely.
        """
        if not journey:
            return
        if journey.status == JourneyStatus.COMPLETED and journey.dwell_time is not None:
            self.dwell_analytics.record_dwell(journey.dwell_time)

    def stop_session(self, session_id: str) -> Optional[SessionSummary]:
        """
        Stop active monitoring session and generate immutable SessionSummary snapshot.
        If already stopped, returns historical frozen summary snapshot.
        """
        with self._lock:
            if session_id in self._stopped_summaries:
                return self._stopped_summaries[session_id]

        session = self.session_manager.get_session(session_id)
        if not session:
            return None

        # Execute transition to STOPPED
        self.session_manager.stop_session(session_id)

        # Generate summary metrics
        start_ts = session.started_at
        stop_ts = session.stopped_at or datetime.now(timezone.utc).isoformat()
        dur_sec = 0.0
        if start_ts:
            try:
                t0 = datetime.fromisoformat(start_ts.replace("Z", "+00:00")).timestamp()
                t1 = datetime.fromisoformat(stop_ts.replace("Z", "+00:00")).timestamp()
                dur_sec = max(0.0, t1 - t0)
            except Exception:
                dur_sec = 0.0

        venue_flow = self.flow_analytics.get_venue_flow()
        occ_summary = self.occupancy_analytics.get_summary()
        dwell_metrics = self.dwell_analytics.get_metrics()
        peaks = self.peak_tracker.get_peaks()

        all_alerts = self.alert_manager.get_all_alerts()
        resolved_alerts = self.alert_manager.get_resolved_alerts()

        avg_entry_rate = (venue_flow.cumulative_entries / (dur_sec / 60.0)) if dur_sec > 60 else venue_flow.entry_rate_5m
        avg_exit_rate = (venue_flow.cumulative_exits / (dur_sec / 60.0)) if dur_sec > 60 else venue_flow.exit_rate_5m

        summary = SessionSummary(
            session_id=session_id,
            venue_id=self.venue_id,
            started_at=start_ts,
            stopped_at=stop_ts,
            duration_seconds=round(dur_sec, 2),
            total_entries=venue_flow.cumulative_entries,
            total_exits=venue_flow.cumulative_exits,
            peak_occupancy=peaks.peak_occupancy,
            peak_occupancy_timestamp=peaks.peak_occupancy_timestamp,
            average_entry_rate=round(avg_entry_rate, 2),
            peak_entry_rate=peaks.peak_entry_rate,
            average_exit_rate=round(avg_exit_rate, 2),
            peak_exit_rate=peaks.peak_exit_rate,
            average_dwell=dwell_metrics.average_dwell,
            median_dwell=dwell_metrics.median_dwell,
            p95_dwell=dwell_metrics.p95_dwell,
            busiest_gate=occ_summary.busiest_gate,
            least_active_gate=occ_summary.least_active_gate,
            peak_congestion=peaks.peak_congestion_level.value if isinstance(peaks.peak_congestion_level, Enum) else str(peaks.peak_congestion_level),
            total_alerts_created=len(all_alerts),
            total_alerts_resolved=len(resolved_alerts)
        )

        with self._lock:
            self._stopped_summaries[session_id] = summary

        intelligence_logger.info(
            f"Session {session_id} stopped. Frozen SessionSummary snapshot created.",
            extra={"session_id": session_id, "duration_seconds": dur_sec, "total_entries": summary.total_entries}
        )

        return summary

    def get_current_intelligence(self) -> Dict[str, Any]:
        venue_flow = self.flow_analytics.get_venue_flow()
        occ_summary = self.occupancy_analytics.get_summary()
        density_state = self.density_analytics.evaluate(occ_summary.current_occupancy, venue_flow.net_flow_rate_5m)
        dwell_metrics = self.dwell_analytics.get_metrics()
        peaks = self.peak_tracker.get_peaks()

        return {
            "venue_id": self.venue_id,
            "flow": venue_flow.to_dict(),
            "occupancy": occ_summary.to_dict(),
            "density": density_state.to_dict(),
            "dwell": dwell_metrics.to_dict(),
            "peaks": peaks.to_dict(),
            "active_alerts_count": len(self.alert_manager.get_active_alerts()),
            "metrics": self.metrics.get_metrics()
        }

    def reset_all(self) -> None:
        with self._lock:
            self.session_manager.clear()
            self.flow_analytics.reset()
            self.occupancy_analytics.reset()
            self.density_analytics.reset()
            self.dwell_analytics.reset()
            self.peak_tracker.reset()
            self.anomaly_detector.reset()
            self.alert_manager.reset()
            self.metrics.reset()
            self._stopped_summaries.clear()

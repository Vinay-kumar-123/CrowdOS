"""
Thread-safe Rule-Based Anomaly Detector.
Evaluates flow rates, occupancy spikes, flow imbalance, and stagnation.
Uses sustained-condition counting to prevent single-event noise or alert spam.
"""
import threading
from typing import List, Dict, Optional
from intelligence.anomaly.rules import AnomalyType, AnomalySignal
from intelligence.analytics.flow import FlowMetrics
from intelligence.analytics.occupancy import OccupancyAnalyticsSummary
from intelligence.config.thresholds import CrowdThresholdConfig, CongestionThresholdConfig


class AnomalyDetector:
    """
    Evaluates operational metrics against deterministic anomaly rules.
    """

    def __init__(
        self,
        crowd_config: Optional[CrowdThresholdConfig] = None,
        congestion_config: Optional[CongestionThresholdConfig] = None,
        sustained_frames_required: int = 2
    ):
        self.crowd_config = crowd_config or CrowdThresholdConfig()
        self.congestion_config = congestion_config or CongestionThresholdConfig()
        self.sustained_frames_required = max(1, sustained_frames_required)

        # Counter for sustained anomaly conditions: rule_key -> count
        self._sustained_counters: Dict[str, int] = {}
        self._lock = threading.Lock()

    def evaluate_anomalies(
        self,
        venue_flow: FlowMetrics,
        occupancy_summary: OccupancyAnalyticsSummary,
        gate_flows: Optional[Dict[str, FlowMetrics]] = None
    ) -> List[AnomalySignal]:
        signals = []

        with self._lock:
            # 1. ENTRY_SURGE
            entry_rate = venue_flow.entry_rate_5m
            surge_thresh = self.congestion_config.surge_entry_rate
            key_surge = "ENTRY_SURGE:GLOBAL"
            if entry_rate >= surge_thresh:
                self._sustained_counters[key_surge] = self._sustained_counters.get(key_surge, 0) + 1
                if self._sustained_counters[key_surge] >= self.sustained_frames_required:
                    signals.append(AnomalySignal(
                        anomaly_type=AnomalyType.ENTRY_SURGE,
                        venue_id=venue_flow.venue_id,
                        description=f"Sustained entry surge: {entry_rate:.1f} persons/min (threshold={surge_thresh})",
                        severity="HIGH" if entry_rate > surge_thresh * 1.5 else "MEDIUM",
                        value=entry_rate,
                        threshold=surge_thresh
                    ))
            else:
                self._sustained_counters[key_surge] = 0

            # 2. EXIT_SURGE
            exit_rate = venue_flow.exit_rate_5m
            exit_thresh = self.congestion_config.surge_exit_rate
            key_exit = "EXIT_SURGE:GLOBAL"
            if exit_rate >= exit_thresh:
                self._sustained_counters[key_exit] = self._sustained_counters.get(key_exit, 0) + 1
                if self._sustained_counters[key_exit] >= self.sustained_frames_required:
                    signals.append(AnomalySignal(
                        anomaly_type=AnomalyType.EXIT_SURGE,
                        venue_id=venue_flow.venue_id,
                        description=f"Sustained exit surge: {exit_rate:.1f} persons/min (threshold={exit_thresh})",
                        severity="HIGH" if exit_rate > exit_thresh * 1.5 else "MEDIUM",
                        value=exit_rate,
                        threshold=exit_thresh
                    ))
            else:
                self._sustained_counters[key_exit] = 0

            # 3. OCCUPANCY_SPIKE
            occupancy = occupancy_summary.current_occupancy
            spike_thresh = self.crowd_config.critical_min
            key_spike = "OCCUPANCY_SPIKE:GLOBAL"
            if occupancy >= spike_thresh:
                self._sustained_counters[key_spike] = self._sustained_counters.get(key_spike, 0) + 1
                if self._sustained_counters[key_spike] >= self.sustained_frames_required:
                    signals.append(AnomalySignal(
                        anomaly_type=AnomalyType.OCCUPANCY_SPIKE,
                        venue_id=venue_flow.venue_id,
                        description=f"Critical occupancy spike: {occupancy} persons (threshold={spike_thresh})",
                        severity="CRITICAL",
                        value=float(occupancy),
                        threshold=float(spike_thresh)
                    ))
            else:
                self._sustained_counters[key_spike] = 0

            # 4. MOVEMENT_STAGNATION
            # Signal: High venue occupancy (> low_max) but flow rates drop to 0.0
            key_stag = "MOVEMENT_STAGNATION:GLOBAL"
            if occupancy > self.crowd_config.low_max and (entry_rate + exit_rate) == 0.0:
                self._sustained_counters[key_stag] = self._sustained_counters.get(key_stag, 0) + 1
                if self._sustained_counters[key_stag] >= self.sustained_frames_required:
                    signals.append(AnomalySignal(
                        anomaly_type=AnomalyType.MOVEMENT_STAGNATION,
                        venue_id=venue_flow.venue_id,
                        description=f"Movement stagnation detected: occupancy={occupancy} with zero flow activity",
                        severity="MEDIUM",
                        value=float(occupancy),
                        threshold=float(self.crowd_config.low_max)
                    ))
            else:
                self._sustained_counters[key_stag] = 0

            # 5. GATE_FLOW_ANOMALY
            # Signal: Single gate handling > 75% of overall venue flow when > 1 gate exists
            if gate_flows and len(gate_flows) > 1:
                total_gate_entries = sum(gf.cumulative_entries for gf in gate_flows.values())
                if total_gate_entries >= 10:
                    for gid, gf in gate_flows.items():
                        ratio = gf.cumulative_entries / total_gate_entries
                        key_gate = f"GATE_FLOW_ANOMALY:{gid}"
                        if ratio >= 0.75:
                            self._sustained_counters[key_gate] = self._sustained_counters.get(key_gate, 0) + 1
                            if self._sustained_counters[key_gate] >= self.sustained_frames_required:
                                signals.append(AnomalySignal(
                                    anomaly_type=AnomalyType.GATE_FLOW_ANOMALY,
                                    venue_id=venue_flow.venue_id,
                                    gate_id=gid,
                                    description=f"Gate flow imbalance: gate {gid} handling {ratio*100:.1f}% of total venue entries",
                                    severity="HIGH",
                                    value=ratio * 100.0,
                                    threshold=75.0
                                ))
                        else:
                            self._sustained_counters[key_gate] = 0

        return signals

    def reset(self) -> None:
        with self._lock:
            self._sustained_counters.clear()

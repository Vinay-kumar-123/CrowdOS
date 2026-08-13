"""
Tests for Anomaly Detection (ENTRY_SURGE, EXIT_SURGE, SPIKE, STAGNATION, GATE_FLOW, sustained conditions).
"""
import pytest
from intelligence.config.thresholds import CrowdThresholdConfig, CongestionThresholdConfig
from intelligence.anomaly.detector import AnomalyDetector
from intelligence.analytics.flow import FlowMetrics
from intelligence.analytics.occupancy import OccupancyAnalyticsSummary


def test_entry_surge_anomaly_requires_sustained_condition():
    detector = AnomalyDetector(
        congestion_config=CongestionThresholdConfig(surge_entry_rate=20.0),
        sustained_frames_required=2
    )
    flow = FlowMetrics(entry_rate_5m=25.0)
    occ = OccupancyAnalyticsSummary()

    # Frame 1: count=1 < sustained 2 -> No signal yet
    signals1 = detector.evaluate_anomalies(flow, occ)
    assert len(signals1) == 0

    # Frame 2: count=2 >= sustained 2 -> Anomaly emitted
    signals2 = detector.evaluate_anomalies(flow, occ)
    assert len(signals2) == 1
    assert signals2[0].anomaly_type.value == "ENTRY_SURGE"


def test_occupancy_spike_anomaly():
    detector = AnomalyDetector(
        crowd_config=CrowdThresholdConfig(critical_min=301),
        sustained_frames_required=1
    )
    flow = FlowMetrics()
    occ = OccupancyAnalyticsSummary(current_occupancy=350)

    signals = detector.evaluate_anomalies(flow, occ)
    assert len(signals) >= 1
    types = [s.anomaly_type.value for s in signals]
    assert "OCCUPANCY_SPIKE" in types


def test_movement_stagnation_anomaly():
    """High occupancy (> low_max) with 0.0 flow rate triggers MOVEMENT_STAGNATION."""
    detector = AnomalyDetector(
        crowd_config=CrowdThresholdConfig(low_max=50),
        sustained_frames_required=1
    )
    flow = FlowMetrics(entry_rate_5m=0.0, exit_rate_5m=0.0)
    occ = OccupancyAnalyticsSummary(current_occupancy=100)

    signals = detector.evaluate_anomalies(flow, occ)
    types = [s.anomaly_type.value for s in signals]
    assert "MOVEMENT_STAGNATION" in types


def test_gate_flow_imbalance_anomaly():
    detector = AnomalyDetector(sustained_frames_required=1)
    flow_v = FlowMetrics()
    occ = OccupancyAnalyticsSummary()

    gate_flows = {
        "gate_A": FlowMetrics(cumulative_entries=80),
        "gate_B": FlowMetrics(cumulative_entries=20)
    }

    signals = detector.evaluate_anomalies(flow_v, occ, gate_flows=gate_flows)
    types = [s.anomaly_type.value for s in signals]
    assert "GATE_FLOW_ANOMALY" in types

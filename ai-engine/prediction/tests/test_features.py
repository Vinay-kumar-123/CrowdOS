"""
test_features.py — Tests for feature extraction layer.
"""
import pytest
from prediction.features.feature_extractor import FeatureExtractor
from prediction.features.normalization import (
    compute_anomaly_pressure, compute_gate_imbalance,
    map_density_level, map_congestion_level,
)
from prediction.tests.conftest import make_snapshot, make_gate


@pytest.fixture
def extractor():
    return FeatureExtractor()


# ---------------------------------------------------------------------------
# Occupancy ratio
# ---------------------------------------------------------------------------

def test_occupancy_ratio_normal(extractor):
    snap = make_snapshot(current_occupancy=500, venue_capacity=1000)
    fv = extractor.extract(snap)
    assert fv.occupancy_ratio.normalized_value == pytest.approx(0.5, abs=0.01)
    assert not fv.occupancy_ratio.feature_unavailable


def test_occupancy_ratio_zero_capacity(extractor):
    snap = make_snapshot(current_occupancy=0, venue_capacity=0)
    fv = extractor.extract(snap)
    assert fv.occupancy_ratio.feature_unavailable
    assert fv.occupancy_ratio.normalized_value == 0.0
    assert "zero" in fv.occupancy_ratio.unavailable_reason.lower()


def test_occupancy_ratio_over_capacity(extractor):
    # occupancy > capacity is physically valid (e.g. uncounted entries)
    snap = make_snapshot(current_occupancy=1100, venue_capacity=1000)
    fv = extractor.extract(snap)
    assert not fv.occupancy_ratio.feature_unavailable
    assert fv.occupancy_ratio.normalized_value > 1.0  # over-capacity signal preserved
    assert fv.occupancy_ratio.normalized_value <= 2.0  # clamped at 2.0


# ---------------------------------------------------------------------------
# Entry / Exit pressure
# ---------------------------------------------------------------------------

def test_entry_pressure_normal(extractor):
    snap = make_snapshot(entry_rate_5m=20.0)  # = safe rate → ratio 1.0
    fv = extractor.extract(snap)
    assert fv.entry_pressure.normalized_value == pytest.approx(1.0, abs=0.01)


def test_entry_pressure_zero(extractor):
    snap = make_snapshot(entry_rate_5m=0.0)
    fv = extractor.extract(snap)
    assert fv.entry_pressure.normalized_value == 0.0


def test_exit_pressure_normal(extractor):
    snap = make_snapshot(exit_rate_5m=10.0)
    fv = extractor.extract(snap)
    assert fv.exit_pressure.normalized_value == pytest.approx(0.5, abs=0.01)


# ---------------------------------------------------------------------------
# Net inflow pressure — SIGNED (CTO mandated)
# ---------------------------------------------------------------------------

def test_net_inflow_pressure_positive(extractor):
    snap = make_snapshot(net_flow_rate_5m=15.0)  # = safe rate → 1.0
    fv = extractor.extract(snap)
    assert fv.net_inflow_pressure.normalized_value > 0.0


def test_net_inflow_pressure_negative_preserved(extractor):
    """Negative net flow MUST be preserved, not zeroed."""
    snap = make_snapshot(net_flow_rate_5m=-10.0)
    fv = extractor.extract(snap)
    assert fv.net_inflow_pressure.normalized_value < 0.0
    assert not fv.net_inflow_pressure.feature_unavailable


def test_net_inflow_pressure_zero(extractor):
    snap = make_snapshot(net_flow_rate_5m=0.0)
    fv = extractor.extract(snap)
    assert fv.net_inflow_pressure.normalized_value == 0.0


# ---------------------------------------------------------------------------
# Density and congestion level mapping
# ---------------------------------------------------------------------------

def test_density_level_mapping():
    assert map_density_level("LOW") == pytest.approx(0.1)
    assert map_density_level("MODERATE") == pytest.approx(0.4)
    assert map_density_level("HIGH") == pytest.approx(0.75)
    assert map_density_level("CRITICAL") == pytest.approx(1.0)


def test_congestion_level_mapping():
    assert map_congestion_level("NORMAL") == pytest.approx(0.0)
    assert map_congestion_level("BUILDING") == pytest.approx(0.33)
    assert map_congestion_level("CONGESTED") == pytest.approx(0.67)
    assert map_congestion_level("SEVERE_CONGESTION") == pytest.approx(1.0)


def test_unknown_density_defaults_to_low():
    assert map_density_level("UNKNOWN_LEVEL") == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# Anomaly pressure
# ---------------------------------------------------------------------------

def test_anomaly_pressure_no_anomalies():
    assert compute_anomaly_pressure([]) == 0.0


def test_anomaly_pressure_single_critical():
    result = compute_anomaly_pressure([{"severity": "CRITICAL", "gate_id": "G1"}])
    assert result == pytest.approx(1.0 / 5.0, abs=0.01)


def test_anomaly_pressure_clamped_to_1():
    # 20 CRITICAL anomalies → sum=20, max_score=5 → would exceed 1.0 → clamped
    anomalies = [{"severity": "CRITICAL", "gate_id": f"G{i}"} for i in range(20)]
    result = compute_anomaly_pressure(anomalies)
    assert result == pytest.approx(1.0)


def test_anomaly_pressure_per_gate_independent():
    # Same type at two gates counts twice
    anomalies = [
        {"anomaly_type": "ENTRY_SURGE", "severity": "MEDIUM", "gate_id": "G1"},
        {"anomaly_type": "ENTRY_SURGE", "severity": "MEDIUM", "gate_id": "G2"},
    ]
    result = compute_anomaly_pressure(anomalies, max_score=5.0)
    # Two MEDIUM (0.5 each) = 1.0 / 5.0 = 0.2
    assert result == pytest.approx(0.2, abs=0.01)


def test_anomaly_pressure_mixed_severity():
    anomalies = [
        {"severity": "INFO"},     # 0.1
        {"severity": "HIGH"},     # 0.8
        {"severity": "CRITICAL"}, # 1.0
    ]
    total = 1.9
    result = compute_anomaly_pressure(anomalies, max_score=5.0)
    assert result == pytest.approx(total / 5.0, abs=0.01)


# ---------------------------------------------------------------------------
# Gate imbalance
# ---------------------------------------------------------------------------

def test_gate_imbalance_no_gates():
    assert compute_gate_imbalance([]) == 0.0


def test_gate_imbalance_single_gate():
    assert compute_gate_imbalance([10.0]) == 0.0


def test_gate_imbalance_equal_gates():
    # All equal → max == avg → imbalance = 0
    assert compute_gate_imbalance([5.0, 5.0, 5.0]) == pytest.approx(0.0)


def test_gate_imbalance_high():
    # G1=30, G2=10, G3=10 → avg=16.67, max=30 → imbalance = (30-16.67)/16.67 ≈ 0.8
    gi = compute_gate_imbalance([30.0, 10.0, 10.0])
    assert gi > 0.5


def test_gate_imbalance_inactive_included():
    # Inactive gate (rate=0) is included as 0.0
    gi_with = compute_gate_imbalance([10.0, 0.0])
    gi_without = compute_gate_imbalance([10.0])
    assert gi_with != gi_without  # including 0.0 changes the average
    assert gi_with > 0.0


def test_gate_imbalance_10_gates(extractor):
    gates = {f"G{i}": make_gate(f"G{i}", entry_rate=float(i + 1)) for i in range(10)}
    snap = make_snapshot(gate_snapshots=gates)
    fv = extractor.extract(snap)
    assert not fv.gate_imbalance.feature_unavailable
    assert fv.gate_imbalance.raw_value >= 0.0


def test_gate_imbalance_100_gates(extractor):
    gates = {f"G{i}": make_gate(f"G{i}", entry_rate=float(i + 1)) for i in range(100)}
    snap = make_snapshot(gate_snapshots=gates)
    fv = extractor.extract(snap)
    assert fv.gate_imbalance.raw_value >= 0.0
    assert not fv.gate_imbalance.feature_unavailable


# ---------------------------------------------------------------------------
# Dwell pressure
# ---------------------------------------------------------------------------

def test_dwell_pressure_normal(extractor):
    snap = make_snapshot(average_dwell=900.0)  # half of safe_dwell (1800s)
    fv = extractor.extract(snap)
    assert fv.dwell_pressure.normalized_value == pytest.approx(0.5, abs=0.01)


def test_dwell_pressure_zero(extractor):
    snap = make_snapshot(average_dwell=0.0)
    fv = extractor.extract(snap)
    assert fv.dwell_pressure.normalized_value == 0.0


# ---------------------------------------------------------------------------
# All 9 features present
# ---------------------------------------------------------------------------

def test_all_9_features_present(extractor):
    snap = make_snapshot()
    fv = extractor.extract(snap)
    feature_names = {
        "occupancy_ratio", "entry_pressure", "exit_pressure",
        "net_inflow_pressure", "density_score", "congestion_score",
        "anomaly_pressure", "gate_imbalance", "dwell_pressure"
    }
    assert set(fv.to_dict()["features"].keys()) == feature_names

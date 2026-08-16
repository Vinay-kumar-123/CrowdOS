"""
test_multi_gate.py — Tests for multi-gate risk and decision handling (1, 3, 10, 100 gates).
"""
import pytest
from prediction.engine.prediction_engine import PredictionEngine
from prediction.tests.conftest import make_snapshot, make_gate, make_ts


@pytest.fixture
def engine():
    e = PredictionEngine(venue_id="test-venue")
    yield e
    e.reset()


def test_single_gate(engine):
    gates = {"G1": make_gate("G1", entry_rate=10.0, occupancy=100)}
    snap = make_snapshot(gate_snapshots=gates, timestamp=make_ts(0))
    res = engine.predict(snap)
    assert "G1" in res.gate_results
    assert res.gate_results["G1"]["gate_id"] == "G1"
    assert "risk" in res.gate_results["G1"]


def test_three_gates_independent(engine):
    gates = {
        "G1_calm": make_gate("G1_calm", entry_rate=2.0, occupancy=20),
        "G2_busy": make_gate("G2_busy", entry_rate=25.0, occupancy=250),
        "G3_calm": make_gate("G3_calm", entry_rate=3.0, occupancy=30),
    }
    snap = make_snapshot(gate_snapshots=gates, timestamp=make_ts(0))
    res = engine.predict(snap)
    
    assert len(res.gate_results) == 3
    # G2_busy should have higher risk score than G1_calm
    score_calm = res.gate_results["G1_calm"]["risk"]["score"]
    score_busy = res.gate_results["G2_busy"]["risk"]["score"]
    assert score_busy > score_calm


def test_ten_gates(engine):
    gates = {f"G{i}": make_gate(f"G{i}", entry_rate=float(i + 1), occupancy=(i + 1) * 10) for i in range(10)}
    snap = make_snapshot(gate_snapshots=gates, timestamp=make_ts(0))
    res = engine.predict(snap)
    assert len(res.gate_results) == 10
    for i in range(10):
        assert f"G{i}" in res.gate_results


def test_hundred_gates(engine):
    gates = {f"G{i}": make_gate(f"G{i}", entry_rate=float((i % 20) + 1), occupancy=(i + 1) * 5) for i in range(100)}
    snap = make_snapshot(gate_snapshots=gates, timestamp=make_ts(0))
    res = engine.predict(snap)
    assert len(res.gate_results) == 100
    assert res.processing_time_ms < 500.0  # must execute fast in memory


def test_gate_state_isolation(engine):
    # Gate 1 has severe entries, Gate 2 has zero entries
    gates = {
        "G1": make_gate("G1", entry_rate=30.0),
        "G2": make_gate("G2", entry_rate=0.0),
    }
    # Run 3 frames
    for i in range(3):
        snap = make_snapshot(gate_snapshots=gates, timestamp=make_ts(i * 30))
        res = engine.predict(snap)
    
    # G1 risk should be high, G2 risk should be low
    g1_res = res.gate_results["G1"]
    g2_res = res.gate_results["G2"]
    assert g1_res["risk"]["score"] > g2_res["risk"]["score"]

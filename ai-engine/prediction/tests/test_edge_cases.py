"""
test_edge_cases.py — Tests covering all mandatory edge cases from Sprint 8 spec.
"""
import math
import pytest
from prediction.engine.prediction_engine import PredictionEngine
from prediction.features.snapshot import PredictionInputSnapshot, GateInputSnapshot
from prediction.tests.conftest import make_snapshot, make_gate, make_ts


@pytest.fixture
def engine():
    e = PredictionEngine(venue_id="edge-venue")
    yield e
    e.reset()


# 1. Zero capacity
def test_edge_01_zero_capacity(engine):
    snap = make_snapshot(current_occupancy=0, venue_capacity=0, timestamp=make_ts(0))
    res = engine.predict(snap)
    assert res.status == "ok"
    # occupancy_ratio should be marked unavailable, no division by zero error
    factor = next(f for f in res.venue_risk.factors if f.name == "occupancy_ratio")
    assert factor.feature_unavailable is True


# 2. Zero occupancy
def test_edge_02_zero_occupancy(engine):
    snap = make_snapshot(current_occupancy=0, timestamp=make_ts(0))
    res = engine.predict(snap)
    assert res.status == "ok"
    assert res.venue_risk.score < 20.0


# 3. Occupancy above capacity
def test_edge_03_occupancy_above_capacity(engine):
    snap = make_snapshot(current_occupancy=1200, venue_capacity=1000, timestamp=make_ts(0))
    res = engine.predict(snap)
    assert res.status == "ok"
    assert res.venue_risk.score > 0.0


# 4. Negative occupancy -> Invalid input
def test_edge_04_negative_occupancy():
    with pytest.raises(ValueError, match="INVALID_INPUT.*current_occupancy"):
        make_snapshot(current_occupancy=-50)


# 5. Negative entry rate -> Invalid input
def test_edge_05_negative_entry_rate():
    with pytest.raises(ValueError, match="INVALID_INPUT.*entry_rate"):
        make_snapshot(entry_rate_5m=-10.0)


# 6. Negative exit rate -> Invalid input
def test_edge_06_negative_exit_rate():
    with pytest.raises(ValueError, match="INVALID_INPUT.*exit_rate"):
        make_snapshot(exit_rate_5m=-5.0)


# 7. NaN in numeric field -> Invalid input
def test_edge_07_nan_field():
    with pytest.raises(ValueError, match="INVALID_INPUT.*NaN"):
        make_snapshot(entry_rate_5m=float("nan"))


# 8. Infinity in numeric field -> Invalid input
def test_edge_08_infinity_field():
    with pytest.raises(ValueError, match="INVALID_INPUT.*Infinity"):
        make_snapshot(entry_rate_5m=float("inf"))


# 9. Negative net flow -> Valid physical behavior
def test_edge_09_negative_net_flow(engine):
    snap = make_snapshot(net_flow_rate_5m=-15.0, timestamp=make_ts(0))
    res = engine.predict(snap)
    assert res.status == "ok"
    factor = next(f for f in res.venue_risk.factors if f.name == "net_inflow_pressure")
    assert factor.normalized_feature_value < 0.0
    assert factor.contribution == 0.0


# 10. Missing gate data
def test_edge_10_missing_gate_data(engine):
    snap = make_snapshot(gate_snapshots={}, timestamp=make_ts(0))
    res = engine.predict(snap)
    assert res.status == "ok"
    assert res.gate_results == {}


# 11. Empty gate set
def test_edge_11_empty_gate_set(engine):
    snap = make_snapshot(gate_snapshots={}, timestamp=make_ts(0))
    res = engine.predict(snap)
    factor = next(f for f in res.venue_risk.factors if f.name == "gate_imbalance")
    assert factor.feature_unavailable is True


# 12. Single gate imbalance = 0.0
def test_edge_12_single_gate_imbalance(engine):
    gates = {"G1": make_gate("G1", entry_rate=20.0)}
    snap = make_snapshot(gate_snapshots=gates, timestamp=make_ts(0))
    res = engine.predict(snap)
    factor = next(f for f in res.venue_risk.factors if f.name == "gate_imbalance")
    assert factor.feature_unavailable is False
    assert factor.normalized_feature_value == 0.0


# 13. 100-gate imbalance calculation
def test_edge_13_hundred_gate_imbalance(engine):
    gates = {f"G{i}": make_gate(f"G{i}", entry_rate=float(i)) for i in range(100)}
    snap = make_snapshot(gate_snapshots=gates, timestamp=make_ts(0))
    res = engine.predict(snap)
    factor = next(f for f in res.venue_risk.factors if f.name == "gate_imbalance")
    assert factor.normalized_feature_value > 0.0


# 14. Duplicate timestamp rejection
def test_edge_14_duplicate_timestamp(engine):
    snap = make_snapshot(timestamp=make_ts(0))
    res1 = engine.predict(snap)
    res2 = engine.predict(snap)
    assert res1.status == "ok"
    assert res2.status == "duplicate"


# 15. Out-of-order timestamps handled in trend
def test_edge_15_out_of_order_timestamps(engine):
    snap1 = make_snapshot(timestamp=make_ts(60), current_occupancy=200)
    snap2 = make_snapshot(timestamp=make_ts(0), current_occupancy=100)
    snap3 = make_snapshot(timestamp=make_ts(30), current_occupancy=150)
    engine.predict(snap1)
    engine.predict(snap2)
    res3 = engine.predict(snap3)
    assert res3.status == "ok"


# 16. Insufficient forecast history
def test_edge_16_insufficient_forecast_history(engine):
    snap = make_snapshot(timestamp=make_ts(0))
    res = engine.predict(snap)
    assert res.occupancy_forecast.forecasts[0].status.value == "INSUFFICIENT_DATA"


# 17. Constant history -> slope = 0, STABLE
def test_edge_17_constant_history(engine):
    for i in range(5):
        snap = make_snapshot(current_occupancy=200, timestamp=make_ts(i * 30))
        res = engine.predict(snap)
    assert res.venue_trend.direction.value == "STABLE"


# 18. Rapidly increasing occupancy
def test_edge_18_rapidly_increasing_occupancy(engine):
    for i in range(6):
        snap = make_snapshot(current_occupancy=100 + i * 150, timestamp=make_ts(i * 30))
        res = engine.predict(snap)
    assert res.venue_trend.direction.value == "INCREASING"


# 19. Rapidly decreasing occupancy
def test_edge_19_rapidly_decreasing_occupancy(engine):
    for i in range(6):
        snap = make_snapshot(current_occupancy=900 - i * 120, timestamp=make_ts(i * 30))
        res = engine.predict(snap)
    assert res.venue_trend.direction.value == "DECREASING"


# 20. Conflicting gate signals
def test_edge_20_conflicting_gate_signals(engine):
    gates = {
        "G_HIGH": make_gate("G_HIGH", entry_rate=40.0),
        "G_LOW": make_gate("G_LOW", entry_rate=0.0),
    }
    snap = make_snapshot(gate_snapshots=gates, timestamp=make_ts(0))
    res = engine.predict(snap)
    assert "G_HIGH" in res.gate_results
    assert "G_LOW" in res.gate_results
    assert res.gate_results["G_HIGH"]["risk"]["score"] > res.gate_results["G_LOW"]["risk"]["score"]


# 21. Expired session
def test_edge_21_expired_session(engine):
    snap = make_snapshot(session_status="EXPIRED", timestamp=make_ts(0))
    res = engine.predict(snap)
    assert res.status == "skipped"


# 22. Stopped session
def test_edge_22_stopped_session(engine):
    snap = make_snapshot(session_status="STOPPED", timestamp=make_ts(0))
    res = engine.predict(snap)
    assert res.status == "skipped"


# 23. Malformed input / negative capacity
def test_edge_23_negative_capacity():
    with pytest.raises(ValueError, match="INVALID_CONFIGURATION.*venue_capacity"):
        make_snapshot(venue_capacity=-100)


# 24. Duplicate prediction event key
def test_edge_24_duplicate_event_key(engine):
    snap = make_snapshot(session_id="S_DUP", timestamp=make_ts(10))
    assert engine.predict(snap).status == "ok"
    assert engine.predict(snap).status == "duplicate"


# 25. Biometric metadata leakage check
def test_edge_25_biometric_leakage():
    # Verify PredictionInputSnapshot rejects forbidden fields
    fields = PredictionInputSnapshot.model_fields.keys()
    forbidden = {"face_crop", "embedding", "biometric", "raw_image", "feature_vector_raw"}
    for f in forbidden:
        assert f not in fields

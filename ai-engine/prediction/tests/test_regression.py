"""
test_regression.py — Tests for regression, backward compatibility, privacy and deterministic guarantees.
"""
import pytest
from prediction.engine.prediction_engine import PredictionEngine
from prediction.features.snapshot import PredictionInputSnapshot, GateInputSnapshot
from prediction.tests.conftest import make_snapshot, make_gate, make_ts

# Test Sprint 7 interface consumption compatibility
from intelligence.analytics.flow import FlowMetrics
from intelligence.analytics.occupancy import OccupancyAnalyticsSummary
from intelligence.analytics.density import DensityState
from intelligence.analytics.dwell import DwellMetrics
from intelligence.analytics.peak import PeakMetrics


def test_consumption_from_sprint7_types():
    # Verify we can seamlessly construct a PredictionInputSnapshot from Sprint 7 dataclasses/models
    flow = FlowMetrics(
        venue_id="ven1",
        entry_rate_5m=12.5,
        exit_rate_5m=8.0,
        net_flow_rate_5m=4.5,
        entry_rate_1m=14.0,
        entry_rate_15m=11.0,
        cumulative_entries=150,
        cumulative_exits=100,
    )
    occ = OccupancyAnalyticsSummary(
        venue_id="ven1",
        current_occupancy=350,
        busiest_gate="G1",
        gate_occupancy={"G1": 200, "G2": 150},
    )
    density = DensityState(
        venue_id="ven1",
        occupancy=350,
        density_level="MODERATE",
        congestion_level="BUILDING",
        occupancy_ratio=0.7,
    )
    dwell = DwellMetrics(
        average_dwell=450.0,
        p95_dwell=900.0,
    )

    snap = PredictionInputSnapshot(
        session_id="sess_regression",
        venue_id="ven1",
        timestamp="2026-01-01T12:00:00Z",
        session_status="ACTIVE",
        venue_capacity=500,
        current_occupancy=occ.current_occupancy,
        total_entries=flow.cumulative_entries,
        total_exits=flow.cumulative_exits,
        busiest_gate=occ.busiest_gate,
        gate_occupancy=occ.gate_occupancy,
        entry_rate_1m=flow.entry_rate_1m,
        entry_rate_5m=flow.entry_rate_5m,
        exit_rate_5m=flow.exit_rate_5m,
        net_flow_rate_5m=flow.net_flow_rate_5m,
        entry_rate_15m=flow.entry_rate_15m,
        density_level=density.density_level if isinstance(density.density_level, str) else density.density_level.value,
        congestion_level=density.congestion_level if isinstance(density.congestion_level, str) else density.congestion_level.value,
        occupancy_ratio=density.occupancy_ratio,
        average_dwell=dwell.average_dwell,
        p95_dwell=dwell.p95_dwell,
    )

    engine = PredictionEngine(venue_id="ven1")
    res = engine.predict(snap)
    assert res.status == "ok"
    assert res.venue_risk is not None


def test_deterministic_output_reproducibility():
    snap = make_snapshot(timestamp=make_ts(0))
    engine1 = PredictionEngine(venue_id="det-venue")
    engine2 = PredictionEngine(venue_id="det-venue")
    
    res1 = engine1.predict(snap)
    res2 = engine2.predict(snap)
    
    assert res1.venue_risk.score == res2.venue_risk.score
    assert res1.venue_risk.risk_level == res2.venue_risk.risk_level
    assert res1.venue_decision.action == res2.venue_decision.action


def test_privacy_allowlist_audit():
    # Verify no biometric vectors exist in exported dictionary
    snap = make_snapshot()
    engine = PredictionEngine(venue_id="priv-venue")
    res = engine.predict(snap)
    res_dict = res.to_dict()
    
    dict_str = str(res_dict).lower()
    forbidden_tokens = ["embedding", "biometric", "face_crop", "vector_512", "identity_token"]
    for tok in forbidden_tokens:
        assert tok not in dict_str

"""
test_engine.py — Tests for PredictionEngine orchestrator.
"""
import pytest
from prediction.engine.prediction_engine import PredictionEngine
from prediction.tests.conftest import make_snapshot, make_gate, make_ts
from prediction.risk.risk_level import RiskLevel


@pytest.fixture
def engine():
    e = PredictionEngine(venue_id="test-venue")
    yield e
    e.reset()


def test_predict_basic_flow(engine):
    snap = make_snapshot(timestamp=make_ts(0))
    res = engine.predict(snap)
    assert res.status == "ok"
    assert res.venue_risk is not None
    assert res.venue_trend is not None
    assert res.venue_decision is not None
    assert res.occupancy_forecast is not None
    assert res.flow_forecast is not None
    assert res.processing_time_ms >= 0.0


def test_predict_stopped_session_skipped(engine):
    snap = make_snapshot(session_status="STOPPED", timestamp=make_ts(0))
    res = engine.predict(snap)
    assert res.status == "skipped"
    assert res.venue_risk is None
    assert "no active predictions" in res.message


def test_predict_expired_session_skipped(engine):
    snap = make_snapshot(session_status="EXPIRED", timestamp=make_ts(0))
    res = engine.predict(snap)
    assert res.status == "skipped"
    assert res.venue_risk is None


def test_predict_paused_session_paused(engine):
    snap = make_snapshot(session_status="PAUSED", timestamp=make_ts(0))
    res = engine.predict(snap)
    assert res.status == "paused"
    assert res.venue_risk is None


def test_predict_idempotency_duplicate_rejected(engine):
    snap1 = make_snapshot(timestamp=make_ts(0))
    res1 = engine.predict(snap1)
    assert res1.status == "ok"

    # Same session + same timestamp
    res2 = engine.predict(snap1)
    assert res2.status == "duplicate"


def test_predict_hysteresis_escalation(engine):
    # Base configuration requires 2 consecutive frames to escalate
    # Frame 1: LOW
    snap1 = make_snapshot(current_occupancy=100, timestamp=make_ts(0))
    res1 = engine.predict(snap1)
    assert res1.venue_risk.risk_level == RiskLevel.LOW

    # Frame 2: Sudden surge to HIGH/CRITICAL (950 occ, high rate, severe congestion) -> first frame of surge
    snap2 = make_snapshot(
        current_occupancy=950,
        entry_rate_5m=30.0,
        net_flow_rate_5m=25.0,
        congestion_level="SEVERE_CONGESTION",
        timestamp=make_ts(30)
    )
    res2 = engine.predict(snap2)
    # Hysteresis prevents instant escalation on single frame
    assert res2.venue_risk.risk_level == RiskLevel.LOW

    # Frame 3: Sustained surge -> second frame -> escalates!
    snap3 = make_snapshot(
        current_occupancy=950,
        entry_rate_5m=30.0,
        net_flow_rate_5m=25.0,
        congestion_level="SEVERE_CONGESTION",
        timestamp=make_ts(60)
    )
    res3 = engine.predict(snap3)
    assert res3.venue_risk.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)


def test_predict_metrics_tracked(engine):
    snap = make_snapshot(timestamp=make_ts(0))
    engine.predict(snap)
    metrics = engine.get_metrics()
    assert metrics["prediction_evaluations"] == 1
    assert metrics["decisions_generated"] == 1
    assert metrics["errors"] == 0
    assert metrics["avg_latency_ms"] >= 0.0


def test_engine_reset(engine):
    snap = make_snapshot(timestamp=make_ts(0))
    engine.predict(snap)
    assert engine.get_metrics()["prediction_evaluations"] == 1
    engine.reset()
    assert engine.get_metrics()["prediction_evaluations"] == 0

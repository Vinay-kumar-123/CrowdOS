"""
test_risk.py — Tests for RiskScorer and RiskResult.
"""
import pytest
from prediction.risk.risk_score import RiskScorer, RiskResult
from prediction.risk.risk_level import RiskLevel, score_to_risk_level
from prediction.features.feature_extractor import FeatureExtractor
from prediction.tests.conftest import make_snapshot


@pytest.fixture
def scorer():
    return RiskScorer()


@pytest.fixture
def extractor():
    return FeatureExtractor()


def test_score_range_0_to_100(scorer, extractor):
    # Minimal snapshot
    snap_low = make_snapshot(
        current_occupancy=0,
        entry_rate_5m=0.0,
        exit_rate_5m=0.0,
        net_flow_rate_5m=0.0,
        density_level="LOW",
        congestion_level="NORMAL",
    )
    fv_low = extractor.extract(snap_low)
    res_low = scorer.score(fv_low)
    assert 0.0 <= res_low.score <= 100.0

    # Max snapshot
    snap_high = make_snapshot(
        current_occupancy=1000,
        venue_capacity=1000,
        entry_rate_5m=100.0,
        exit_rate_5m=0.0,
        net_flow_rate_5m=100.0,
        density_level="CRITICAL",
        congestion_level="SEVERE_CONGESTION",
        active_anomalies=[{"severity": "CRITICAL"} for _ in range(10)],
        average_dwell=3600.0,
    )
    fv_high = extractor.extract(snap_high)
    res_high = scorer.score(fv_high)
    assert 0.0 <= res_high.score <= 100.0
    assert res_high.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)


def test_risk_level_mapping():
    assert score_to_risk_level(0.0) == RiskLevel.LOW
    assert score_to_risk_level(19.9) == RiskLevel.LOW
    assert score_to_risk_level(20.0) == RiskLevel.GUARDED
    assert score_to_risk_level(39.9) == RiskLevel.GUARDED
    assert score_to_risk_level(40.0) == RiskLevel.ELEVATED
    assert score_to_risk_level(59.9) == RiskLevel.ELEVATED
    assert score_to_risk_level(60.0) == RiskLevel.HIGH
    assert score_to_risk_level(79.9) == RiskLevel.HIGH
    assert score_to_risk_level(80.0) == RiskLevel.CRITICAL
    assert score_to_risk_level(100.0) == RiskLevel.CRITICAL


def test_factors_list_completeness(scorer, extractor):
    snap = make_snapshot()
    fv = extractor.extract(snap)
    res = scorer.score(fv)
    assert len(res.factors) == 7
    factor_names = {f.name for f in res.factors}
    expected = {
        "occupancy_ratio", "entry_pressure", "net_inflow_pressure",
        "congestion_score", "anomaly_pressure", "gate_imbalance", "dwell_pressure"
    }
    assert factor_names == expected
    for f in res.factors:
        assert f.weight > 0.0
        assert f.contribution >= 0.0


def test_explanation_non_empty(scorer, extractor):
    snap = make_snapshot()
    fv = extractor.extract(snap)
    res = scorer.score(fv)
    assert isinstance(res.explanation, str)
    assert len(res.explanation) > 0
    assert "Risk level" in res.explanation


def test_negative_net_flow_contributes_zero_risk(scorer, extractor):
    """
    When net flow is negative (exits > entries), it must contribute 0 to risk,
    while preserving signed normalized_value.
    """
    snap = make_snapshot(net_flow_rate_5m=-20.0)
    fv = extractor.extract(snap)
    res = scorer.score(fv)
    net_factor = next(f for f in res.factors if f.name == "net_inflow_pressure")
    assert net_factor.normalized_feature_value < 0.0
    assert net_factor.scoring_value == 0.0
    assert net_factor.contribution == 0.0


def test_data_sufficient_flag(scorer, extractor):
    # Zero capacity causes occupancy_ratio to be unavailable
    snap = make_snapshot(current_occupancy=0, venue_capacity=0)
    fv = extractor.extract(snap)
    res = scorer.score(fv)
    assert res.data_sufficient is False

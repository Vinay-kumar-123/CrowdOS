"""
test_decision.py — Tests for DecisionEngine and decision rule priority.
"""
import pytest
from prediction.decision.decision_engine import DecisionEngine
from prediction.decision.decision_schema import DecisionAction
from prediction.risk.risk_score import RiskResult
from prediction.risk.risk_level import RiskLevel
from prediction.risk.risk_factors import RiskFactor
from prediction.trend.trend_state import TrendResult, TrendDirection, TrendStrength
from prediction.forecast.occupancy_forecast import (
    OccupancyForecastResult, OccupancyForecastPoint, ForecastStatus, ForecastConfidence
)


@pytest.fixture
def decision_engine():
    return DecisionEngine()


def make_test_risk_result(
    level: RiskLevel = RiskLevel.LOW,
    score: float = 10.0,
    entry_pressure: float = 0.5,
    net_inflow_pressure: float = 0.2,
    gate_imbalance: float = 0.1,
) -> RiskResult:
    factors = [
        RiskFactor(name="entry_pressure", normalized_feature_value=entry_pressure, weight=0.15),
        RiskFactor(name="net_inflow_pressure", normalized_feature_value=net_inflow_pressure, weight=0.15),
        RiskFactor(name="gate_imbalance", normalized_feature_value=gate_imbalance, weight=0.05),
    ]
    return RiskResult(
        session_id="s1",
        venue_id="v1",
        timestamp="2026-01-01T12:00:00Z",
        score=score,
        risk_level=level,
        factors=factors,
        explanation="Test explanation",
    )


def make_test_trend_result(
    direction: TrendDirection = TrendDirection.STABLE,
    n_observations: int = 10,
) -> TrendResult:
    return TrendResult(
        session_id="s1",
        venue_id="v1",
        timestamp="2026-01-01T12:00:00Z",
        direction=direction,
        strength=TrendStrength.MODERATE if direction != TrendDirection.INSUFFICIENT_DATA else TrendStrength.UNKNOWN,
        n_observations=n_observations,
    )


def test_low_stable_leads_to_no_action(decision_engine):
    risk = make_test_risk_result(RiskLevel.LOW, score=10.0)
    trend = make_test_trend_result(TrendDirection.STABLE)
    dec = decision_engine.decide(risk, trend, None)
    assert dec.action == DecisionAction.NO_ACTION
    assert "LOW_STABLE_RISK" in dec.reason_codes


def test_guarded_leads_to_monitor(decision_engine):
    risk = make_test_risk_result(RiskLevel.GUARDED, score=30.0)
    trend = make_test_trend_result(TrendDirection.INCREASING)
    dec = decision_engine.decide(risk, trend, None)
    assert dec.action == DecisionAction.MONITOR
    assert "GUARDED_RISK_LEVEL" in dec.reason_codes


def test_elevated_increasing_leads_to_increase_monitoring(decision_engine):
    risk = make_test_risk_result(RiskLevel.ELEVATED, score=50.0)
    trend = make_test_trend_result(TrendDirection.INCREASING)
    dec = decision_engine.decide(risk, trend, None)
    assert dec.action == DecisionAction.INCREASE_MONITORING
    assert "ELEVATED_INCREASING" in dec.reason_codes


def test_high_positive_inflow_leads_to_control_entry(decision_engine):
    risk = make_test_risk_result(RiskLevel.HIGH, score=70.0, net_inflow_pressure=1.2)
    trend = make_test_trend_result(TrendDirection.INCREASING)
    dec = decision_engine.decide(risk, trend, None)
    assert dec.action == DecisionAction.CONTROL_ENTRY
    assert "HIGH_POSITIVE_NET_INFLOW" in dec.reason_codes


def test_high_gate_imbalance_leads_to_redirect_flow(decision_engine):
    # Imbalance = 2.5 (>= high threshold 2.0)
    risk = make_test_risk_result(RiskLevel.HIGH, score=70.0, gate_imbalance=2.5, net_inflow_pressure=1.2)
    trend = make_test_trend_result(TrendDirection.INCREASING)
    dec = decision_engine.decide(risk, trend, None)
    # REDIRECT_FLOW has higher priority (70) than CONTROL_ENTRY (60)
    assert dec.action == DecisionAction.REDIRECT_FLOW
    assert "HIGH_GATE_IMBALANCE" in dec.reason_codes
    assert "CONTROL_ENTRY" in dec.secondary_actions


def test_critical_leads_to_escalate_operator(decision_engine):
    risk = make_test_risk_result(RiskLevel.CRITICAL, score=85.0)
    trend = make_test_trend_result(TrendDirection.STABLE)
    dec = decision_engine.decide(risk, trend, None)
    assert dec.action == DecisionAction.ESCALATE_OPERATOR
    assert "CRITICAL_RISK_LEVEL" in dec.reason_codes


def test_critical_increasing_capacity_exceeded_emergency_review(decision_engine):
    risk = make_test_risk_result(RiskLevel.CRITICAL, score=90.0)
    trend = make_test_trend_result(TrendDirection.INCREASING)
    forecast = OccupancyForecastResult(
        session_id="s1",
        venue_id="v1",
        timestamp="2026-01-01T12:00:00Z",
        venue_capacity=1000,
        forecasts=[
            OccupancyForecastPoint(
                horizon_minutes=5,
                current_value=900,
                projected_value=1100,
                status=ForecastStatus.CAPACITY_EXCEEDED_RISK,
                confidence=ForecastConfidence.MEDIUM,
            )
        ]
    )
    dec = decision_engine.decide(risk, trend, forecast)
    assert dec.action == DecisionAction.EMERGENCY_REVIEW
    assert "CRITICAL_INCREASING_CAPACITY_RISK" in dec.reason_codes
    assert "ESCALATE_OPERATOR" in dec.secondary_actions


def test_disclaimer_present(decision_engine):
    risk = make_test_risk_result(RiskLevel.LOW, score=5.0)
    trend = make_test_trend_result()
    dec = decision_engine.decide(risk, trend, None)
    assert "RECOMMENDATION ONLY" in dec.disclaimer

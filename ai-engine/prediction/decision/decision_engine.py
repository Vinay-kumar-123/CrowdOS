"""
DecisionEngine — Deterministic rule-based operational decision engine.

Evaluates DECISION_RULES in strict priority order.
First matching rule → primary action.
All other matching rules → secondary_actions + reason_codes.
One and only one primary action is returned.

Conflict resolution: explicit priority order prevents ambiguity.
"""
from typing import Optional
from prediction.risk.risk_score import RiskResult
from prediction.trend.trend_state import TrendResult, TrendDirection
from prediction.forecast.occupancy_forecast import OccupancyForecastResult, ForecastStatus
from prediction.decision.decision_schema import DecisionAction, DecisionResult, DECISION_PRIORITY
from prediction.decision.recommendations import DECISION_RULES, build_decision_context
from prediction.config.thresholds import PredictionThresholdsConfig, default_thresholds


class DecisionEngine:
    """Deterministic rule-based decision engine."""

    def __init__(self, config: Optional[PredictionThresholdsConfig] = None):
        self.config = config or default_thresholds
        # Sort rules once at construction (highest priority first)
        self._sorted_rules = sorted(DECISION_RULES, key=lambda r: r.priority, reverse=True)

    def decide(
        self,
        risk_result: RiskResult,
        trend_result: TrendResult,
        forecast_result: Optional[OccupancyForecastResult],
        gate_id: Optional[str] = None,
    ) -> DecisionResult:
        """
        Evaluate rule table and return DecisionResult.
        Primary action = first matching rule.
        All matches contribute reason_codes.
        """
        risk_level = risk_result.risk_level
        trend_direction = trend_result.direction

        # Extract feature values from risk factors
        entry_pressure_norm = self._get_factor_normalized(risk_result, "entry_pressure")
        net_inflow_norm = self._get_factor_normalized(risk_result, "net_inflow_pressure")
        gate_imbalance_raw = self._get_factor_normalized(risk_result, "gate_imbalance")

        # Check capacity exceeded risk from forecasts
        capacity_exceeded_risk = False
        if forecast_result:
            for f in forecast_result.forecasts:
                if f.status == ForecastStatus.CAPACITY_EXCEEDED_RISK:
                    capacity_exceeded_risk = True
                    break

        context = build_decision_context(
            risk_level=risk_level,
            trend_direction=trend_direction,
            entry_pressure_normalized=entry_pressure_norm,
            net_inflow_pressure_normalized=net_inflow_norm,
            gate_imbalance=gate_imbalance_raw,
            high_imbalance_threshold=self.config.features.high_imbalance_threshold,
            capacity_exceeded_risk=capacity_exceeded_risk,
        )

        primary_action: Optional[DecisionAction] = None
        reason_codes = []
        secondary_actions = []

        for rule in self._sorted_rules:
            # Check risk level (empty = any)
            if rule.risk_levels and risk_level not in rule.risk_levels:
                continue
            # Check trend direction (empty = any)
            if rule.trend_directions and trend_direction not in rule.trend_directions:
                continue
            # Check optional condition function
            if rule.condition_fn is not None:
                try:
                    if not rule.condition_fn(context):
                        continue
                except Exception:
                    continue

            # Rule matched
            reason_codes.append(rule.reason_code)
            if primary_action is None:
                primary_action = rule.action
            else:
                if rule.action.value not in secondary_actions:
                    secondary_actions.append(rule.action.value)

        # Default action if no rule matched
        if primary_action is None:
            primary_action = DecisionAction.MONITOR
            reason_codes.append("DEFAULT_MONITOR_NO_RULE_MATCHED")

        # Confidence based on trend data availability
        if trend_result.direction == TrendDirection.INSUFFICIENT_DATA:
            confidence = "INSUFFICIENT_DATA"
        elif trend_result.n_observations >= 20:
            confidence = "HIGH"
        elif trend_result.n_observations >= 10:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        return DecisionResult(
            session_id=risk_result.session_id,
            venue_id=risk_result.venue_id,
            timestamp=risk_result.timestamp,
            action=primary_action,
            priority=DECISION_PRIORITY.get(primary_action, 2),
            reason_codes=reason_codes,
            secondary_actions=secondary_actions,
            risk_score=risk_result.score,
            risk_level=risk_result.risk_level.value,
            gate_id=gate_id,
            confidence=confidence,
        )

    def _get_factor_normalized(self, risk_result: RiskResult, factor_name: str) -> float:
        """Extract normalized_feature_value for a named factor. Returns 0.0 if not found."""
        for f in risk_result.factors:
            if f.name == factor_name:
                v = f.normalized_feature_value
                return v if v is not None else 0.0
        return 0.0

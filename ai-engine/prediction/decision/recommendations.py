"""
Explicit Decision Rule Table for Sprint 8.

Rules are evaluated in strict priority order (highest priority first).
Only ONE primary DecisionAction is returned.
All other matching rules contribute secondary_actions and reason_codes.

CONFLICT RESOLUTION (CTO mandated):
  Priority order (highest = evaluated first, wins primary action):
    90: EMERGENCY_REVIEW   - CRITICAL + INCREASING + capacity_exceeded_risk
    80: ESCALATE_OPERATOR  - CRITICAL (any trend)
    70: REDIRECT_FLOW      - HIGH + gate_imbalance HIGH
    65: REDUCE_GATE_INFLOW - HIGH + INCREASING + entry_pressure > 1.5
    60: CONTROL_ENTRY      - HIGH + (STABLE or INCREASING) + net_flow > 0
    50: INCREASE_MONITORING- HIGH + DECREASING
    45: INCREASE_MONITORING- ELEVATED + INCREASING
    40: MONITOR            - ELEVATED + (STABLE or DECREASING)
    35: MONITOR            - GUARDED (any)
    20: NO_ACTION          - LOW + (STABLE, DECREASING, INSUFFICIENT_DATA)
    Default: MONITOR

GATE IMBALANCE HIGH: gate_imbalance >= high_imbalance_threshold (default 2.0)
ENTRY PRESSURE THRESHOLD: 1.5 (configurable via decision context)
"""
from typing import List, Optional, NamedTuple, Callable
from prediction.risk.risk_level import RiskLevel
from prediction.trend.trend_state import TrendDirection
from prediction.decision.decision_schema import DecisionAction


class RuleCondition(NamedTuple):
    """One explicit decision rule."""
    priority: int            # Higher = evaluated first
    action: DecisionAction
    risk_levels: tuple       # Matching RiskLevel values; empty = any
    trend_directions: tuple  # Matching TrendDirection values; empty = any
    reason_code: str
    condition_fn: Optional[object]  # callable(context: dict) -> bool, or None


# ---------------------------------------------------------------------------
# Decision rule table — explicit, ordered, auditable
# ---------------------------------------------------------------------------
DECISION_RULES: List[RuleCondition] = [
    RuleCondition(
        priority=90,
        action=DecisionAction.EMERGENCY_REVIEW,
        risk_levels=(RiskLevel.CRITICAL,),
        trend_directions=(TrendDirection.INCREASING,),
        reason_code="CRITICAL_INCREASING_CAPACITY_RISK",
        condition_fn=lambda ctx: ctx.get("capacity_exceeded_risk", False),
    ),
    RuleCondition(
        priority=80,
        action=DecisionAction.ESCALATE_OPERATOR,
        risk_levels=(RiskLevel.CRITICAL,),
        trend_directions=(),  # any trend
        reason_code="CRITICAL_RISK_LEVEL",
        condition_fn=None,
    ),
    RuleCondition(
        priority=70,
        action=DecisionAction.REDIRECT_FLOW,
        risk_levels=(RiskLevel.HIGH,),
        trend_directions=(),  # any trend
        reason_code="HIGH_GATE_IMBALANCE",
        condition_fn=lambda ctx: ctx.get("gate_imbalance_high", False),
    ),
    RuleCondition(
        priority=65,
        action=DecisionAction.REDUCE_GATE_INFLOW,
        risk_levels=(RiskLevel.HIGH,),
        trend_directions=(TrendDirection.INCREASING,),
        reason_code="HIGH_INCREASING_ENTRY_PRESSURE",
        condition_fn=lambda ctx: ctx.get("entry_pressure_above_threshold", False),
    ),
    RuleCondition(
        priority=60,
        action=DecisionAction.CONTROL_ENTRY,
        risk_levels=(RiskLevel.HIGH,),
        trend_directions=(TrendDirection.STABLE, TrendDirection.INCREASING),
        reason_code="HIGH_POSITIVE_NET_INFLOW",
        condition_fn=lambda ctx: ctx.get("net_flow_positive", False),
    ),
    RuleCondition(
        priority=50,
        action=DecisionAction.INCREASE_MONITORING,
        risk_levels=(RiskLevel.HIGH,),
        trend_directions=(TrendDirection.DECREASING,),
        reason_code="HIGH_RISK_RECOVERING",
        condition_fn=None,
    ),
    RuleCondition(
        priority=45,
        action=DecisionAction.INCREASE_MONITORING,
        risk_levels=(RiskLevel.ELEVATED,),
        trend_directions=(TrendDirection.INCREASING,),
        reason_code="ELEVATED_INCREASING",
        condition_fn=None,
    ),
    RuleCondition(
        priority=40,
        action=DecisionAction.MONITOR,
        risk_levels=(RiskLevel.ELEVATED,),
        trend_directions=(TrendDirection.STABLE, TrendDirection.DECREASING),
        reason_code="ELEVATED_STABLE_OR_RECOVERING",
        condition_fn=None,
    ),
    RuleCondition(
        priority=35,
        action=DecisionAction.MONITOR,
        risk_levels=(RiskLevel.GUARDED,),
        trend_directions=(),  # any
        reason_code="GUARDED_RISK_LEVEL",
        condition_fn=None,
    ),
    RuleCondition(
        priority=20,
        action=DecisionAction.NO_ACTION,
        risk_levels=(RiskLevel.LOW,),
        trend_directions=(
            TrendDirection.STABLE,
            TrendDirection.DECREASING,
            TrendDirection.INSUFFICIENT_DATA,
        ),
        reason_code="LOW_STABLE_RISK",
        condition_fn=None,
    ),
]


def build_decision_context(
    risk_level: RiskLevel,
    trend_direction: TrendDirection,
    entry_pressure_normalized: float,
    net_inflow_pressure_normalized: float,
    gate_imbalance: float,
    high_imbalance_threshold: float,
    capacity_exceeded_risk: bool,
    entry_pressure_threshold: float = 1.5,
) -> dict:
    """
    Build evaluation context dict for rule condition_fn callables.
    All conditions are explicit and deterministic.
    """
    return {
        "risk_level": risk_level,
        "trend_direction": trend_direction,
        # gate_imbalance HIGH: raw value >= configured threshold
        "gate_imbalance_high": gate_imbalance >= high_imbalance_threshold,
        # entry_pressure_above_threshold: uses normalized_feature_value from RiskResult
        "entry_pressure_above_threshold": entry_pressure_normalized >= entry_pressure_threshold,
        # net_flow_positive: signed normalized_value > 0 (inflow > outflow)
        "net_flow_positive": net_inflow_pressure_normalized > 0.0,
        # capacity_exceeded_risk: any forecast horizon projects over capacity
        "capacity_exceeded_risk": capacity_exceeded_risk,
    }

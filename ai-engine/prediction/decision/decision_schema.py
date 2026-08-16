"""
Decision schema for Sprint 8.

CRITICAL DISCLAIMER:
  DecisionResult contains RECOMMENDATIONS ONLY.
  This AI engine MUST NEVER directly control physical gates, barriers,
  alarms, security systems, or people.
  All actions described are operational suggestions for human operators.
"""
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class DecisionAction(str, Enum):
    NO_ACTION = "NO_ACTION"
    MONITOR = "MONITOR"
    INCREASE_MONITORING = "INCREASE_MONITORING"
    CONTROL_ENTRY = "CONTROL_ENTRY"
    REDIRECT_FLOW = "REDIRECT_FLOW"
    OPEN_ADDITIONAL_GATE = "OPEN_ADDITIONAL_GATE"
    REDUCE_GATE_INFLOW = "REDUCE_GATE_INFLOW"
    ESCALATE_OPERATOR = "ESCALATE_OPERATOR"
    EMERGENCY_REVIEW = "EMERGENCY_REVIEW"


DECISION_PRIORITY = {
    DecisionAction.EMERGENCY_REVIEW: 9,
    DecisionAction.ESCALATE_OPERATOR: 8,
    DecisionAction.REDIRECT_FLOW: 7,
    DecisionAction.REDUCE_GATE_INFLOW: 6,
    DecisionAction.CONTROL_ENTRY: 5,
    DecisionAction.INCREASE_MONITORING: 4,
    DecisionAction.OPEN_ADDITIONAL_GATE: 3,
    DecisionAction.MONITOR: 2,
    DecisionAction.NO_ACTION: 1,
}


class DecisionResult(BaseModel):
    """
    Operational decision recommendation.
    NOT a command to physical infrastructure.
    NOT a guarantee of safety.
    """
    session_id: str
    venue_id: str
    timestamp: str
    action: DecisionAction = Field(default=DecisionAction.MONITOR)
    priority: int = Field(default=2)
    reason_codes: List[str] = Field(default_factory=list)
    secondary_actions: List[str] = Field(
        default_factory=list,
        description="Other rules that also matched (additional context only)"
    )
    risk_score: float = Field(default=0.0)
    risk_level: str = Field(default="LOW")
    gate_id: Optional[str] = Field(default=None)
    confidence: str = Field(default="INSUFFICIENT_DATA")
    disclaimer: str = Field(
        default=(
            "RECOMMENDATION ONLY. "
            "This system does not control physical infrastructure. "
            "Human operator judgment is required."
        )
    )

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

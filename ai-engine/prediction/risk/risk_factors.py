"""
RiskFactor — Per-feature contribution to risk score.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class RiskFactor(BaseModel):
    """Contribution of a single feature to the overall risk score."""
    name: str
    raw_feature_value: Optional[float] = Field(default=None)
    normalized_feature_value: float = Field(default=0.0, description="Value used for risk contribution")
    scoring_value: float = Field(default=0.0, description="Clamped value actually used in score formula")
    weight: float = Field(default=0.0, description="Explicit configured weight")
    contribution: float = Field(default=0.0, description="weight * scoring_value * 100")
    severity: str = Field(default="INFO")
    feature_unavailable: bool = Field(default=False)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


def classify_factor_severity(contribution: float) -> str:
    """Map factor contribution (0–100*weight) to severity label."""
    if contribution >= 15.0:
        return "CRITICAL"
    elif contribution >= 10.0:
        return "HIGH"
    elif contribution >= 5.0:
        return "MEDIUM"
    elif contribution >= 2.0:
        return "LOW"
    return "INFO"

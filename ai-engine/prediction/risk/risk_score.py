"""
RiskScorer — Explainable weighted rule-based risk scoring.

Score formula:
  score = clamp(sum(weight_i * scoring_value_i * 100), 0, 100)

Where scoring_value_i = clamp(normalized_value_i, 0.0, 1.0) for most features.

Net inflow pressure special handling (CTO mandated):
  raw:            net_flow_rate_5m / safe_net_flow_rate  (SIGNED)
  normalized:     signed ratio (preserved in FeatureVector)
  scoring_value:  clamp(normalized, 0.0, 1.0)
    → negative net flow contributes 0 to risk score (net outflow is risk-reducing)
    → positive net flow contributes proportionally
  The negative signal is preserved in FeatureValue.normalized_value for
  decision engine and trend analysis — it is only bounded at the contribution layer.

Every RiskResult exposes:
  - score [0, 100]
  - risk_level
  - factors (7 entries with full provenance)
  - explanation (deterministic template, no LLM)
  - data_sufficient flag
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from prediction.features.feature_vector import FeatureVector
from prediction.features.normalization import clamp
from prediction.risk.risk_level import RiskLevel, score_to_risk_level
from prediction.risk.risk_factors import RiskFactor, classify_factor_severity
from prediction.config.thresholds import PredictionThresholdsConfig, default_thresholds


class RiskResult(BaseModel):
    """Complete, explainable risk evaluation result."""
    session_id: str
    venue_id: str
    timestamp: str
    score: float = Field(default=0.0, description="Risk score 0-100")
    risk_level: RiskLevel = Field(default=RiskLevel.LOW)
    factors: List[RiskFactor] = Field(default_factory=list)
    explanation: str = Field(default="")
    data_sufficient: bool = Field(default=True, description="False if any feature is unavailable")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "venue_id": self.venue_id,
            "timestamp": self.timestamp,
            "score": round(self.score, 2),
            "risk_level": self.risk_level.value,
            "factors": [f.to_dict() for f in self.factors],
            "explanation": self.explanation,
            "data_sufficient": self.data_sufficient,
        }


class RiskScorer:
    """
    Deterministic, explainable risk scorer.
    All weights are explicitly configured — no hidden magic numbers.
    """

    def __init__(self, config: Optional[PredictionThresholdsConfig] = None):
        self.config = config or default_thresholds

    def score(self, fv: FeatureVector) -> RiskResult:
        """Compute RiskResult from FeatureVector."""
        w = self.config.weights
        rl_thresholds = self.config.risk_levels

        # Each entry: (feature_name, weight, FeatureValue object)
        # scoring_value = clamp(normalized_value, 0.0, 1.0) for all features.
        # For net_inflow_pressure: negative normalized_value → scoring_value = 0.0
        # (negative inflow = net outflow = risk-reducing, not risk-adding)
        feature_defs = [
            ("occupancy_ratio",     w.occupancy_ratio,     fv.occupancy_ratio),
            ("entry_pressure",      w.entry_pressure,      fv.entry_pressure),
            ("net_inflow_pressure", w.net_inflow_pressure, fv.net_inflow_pressure),
            ("congestion_score",    w.congestion_score,    fv.congestion_score),
            ("anomaly_pressure",    w.anomaly_pressure,    fv.anomaly_pressure),
            ("gate_imbalance",      w.gate_imbalance,      fv.gate_imbalance),
            ("dwell_pressure",      w.dwell_pressure,      fv.dwell_pressure),
        ]

        total_score = 0.0
        factors: List[RiskFactor] = []

        for name, weight, fval in feature_defs:
            # Clamp to [0, 1] for risk contribution
            # net_inflow_pressure: negative values → 0.0 (no negative risk contribution)
            scoring_val = clamp(fval.normalized_value, 0.0, 1.0)
            contribution = weight * scoring_val * 100.0
            total_score += contribution
            factors.append(RiskFactor(
                name=name,
                raw_feature_value=fval.raw_value,
                normalized_feature_value=fval.normalized_value,  # preserved (signed for net flow)
                scoring_value=round(scoring_val, 4),
                weight=weight,
                contribution=round(contribution, 3),
                severity=classify_factor_severity(contribution),
                feature_unavailable=fval.feature_unavailable,
            ))

        total_score = round(clamp(total_score, 0.0, 100.0), 2)
        risk_level = score_to_risk_level(total_score, rl_thresholds)
        explanation = self._build_explanation(risk_level, factors, fv)
        data_sufficient = not any(f.feature_unavailable for f in factors)

        return RiskResult(
            session_id=fv.session_id,
            venue_id=fv.venue_id,
            timestamp=fv.timestamp,
            score=total_score,
            risk_level=risk_level,
            factors=factors,
            explanation=explanation,
            data_sufficient=data_sufficient,
        )

    def _build_explanation(
        self,
        level: RiskLevel,
        factors: List[RiskFactor],
        fv: FeatureVector
    ) -> str:
        """
        Deterministic template-based explanation.
        No LLM. No hallucinated text.
        """
        available = [f for f in factors if not f.feature_unavailable]
        top = sorted(available, key=lambda x: x.contribution, reverse=True)[:3]
        driver_parts = []
        for f in top:
            if f.contribution >= 1.0:
                driver_parts.append(f"{f.name}={f.normalized_feature_value:.2f} (contribution={f.contribution:.1f})")
        drivers = "; ".join(driver_parts) if driver_parts else "no dominant single factor"

        unavailable = [f.name for f in factors if f.feature_unavailable]
        suffix = f" [{len(unavailable)} feature(s) unavailable: {', '.join(unavailable)}]" if unavailable else ""
        return f"Risk level {level.value}: primary drivers are {drivers}.{suffix}"

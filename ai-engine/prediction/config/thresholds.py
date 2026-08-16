"""
Configurable Thresholds for Sprint 8 Risk Scoring, Trend Detection, and Decision Engine.
All weights and thresholds are explicit and configurable — no hidden constants.
"""
from pydantic import BaseModel, Field, model_validator


class RiskWeightConfig(BaseModel):
    """
    Explicit, configurable risk factor weights.
    Must sum to <= 1.0.
    These weights are publicly documented — nothing is hidden.
    """
    occupancy_ratio: float = Field(default=0.30, description="Weight for occupancy/capacity ratio")
    entry_pressure: float = Field(default=0.15, description="Weight for entry rate pressure")
    net_inflow_pressure: float = Field(default=0.15, description="Weight for net inflow pressure")
    congestion_score: float = Field(default=0.20, description="Weight for congestion level score")
    anomaly_pressure: float = Field(default=0.12, description="Weight for anomaly severity pressure")
    gate_imbalance: float = Field(default=0.05, description="Weight for gate flow imbalance")
    dwell_pressure: float = Field(default=0.03, description="Weight for dwell time pressure")

    @model_validator(mode="after")
    def validate_weights_sum(self):
        total = (
            self.occupancy_ratio + self.entry_pressure + self.net_inflow_pressure
            + self.congestion_score + self.anomaly_pressure + self.gate_imbalance
            + self.dwell_pressure
        )
        if total > 1.0001:
            raise ValueError(f"Risk weights sum to {total:.4f}, must be <= 1.0")
        return self


class RiskLevelThresholds(BaseModel):
    """Configurable risk score ranges. Score [0, 100] -> RiskLevel."""
    guarded_min: float = Field(default=20.0, description="Minimum score for GUARDED level")
    elevated_min: float = Field(default=40.0, description="Minimum score for ELEVATED level")
    high_min: float = Field(default=60.0, description="Minimum score for HIGH level")
    critical_min: float = Field(default=80.0, description="Minimum score for CRITICAL level")


class FeatureThresholds(BaseModel):
    """Safe operating thresholds for feature normalization."""
    safe_entry_rate_per_min: float = Field(default=20.0, description="Persons/min considered safe entry rate")
    safe_exit_rate_per_min: float = Field(default=20.0, description="Persons/min considered safe exit rate")
    safe_net_flow_rate_per_min: float = Field(default=15.0, description="Net flow rate considered safe")
    safe_dwell_seconds: float = Field(default=1800.0, description="Average dwell considered safe (30 min)")
    max_anomaly_score: float = Field(default=5.0, description="Normalization denominator for anomaly pressure")
    high_imbalance_threshold: float = Field(
        default=2.0, description="Gate imbalance ratio >= this value = HIGH imbalance"
    )


class TrendThresholds(BaseModel):
    """Thresholds for trend direction and strength classification."""
    increasing_slope_threshold: float = Field(
        default=0.5, description="Risk score change per minute >= this -> INCREASING"
    )
    decreasing_slope_threshold: float = Field(
        default=-0.5, description="Risk score change per minute <= this -> DECREASING"
    )
    weak_strength_threshold: float = Field(default=1.0, description="|slope| < this -> WEAK trend")
    strong_strength_threshold: float = Field(default=3.0, description="|slope| >= this -> STRONG trend")


class HysteresisConfig(BaseModel):
    """Persistence and hysteresis for risk level transitions."""
    escalation_margin: float = Field(
        default=0.0, description="Extra score margin required above threshold to escalate"
    )
    recovery_margin: float = Field(
        default=3.0, description="Score must drop this many units below threshold before recovery"
    )


class PredictionThresholdsConfig(BaseModel):
    """Master thresholds configuration for Sprint 8 Prediction Engine."""
    weights: RiskWeightConfig = Field(default_factory=RiskWeightConfig)
    risk_levels: RiskLevelThresholds = Field(default_factory=RiskLevelThresholds)
    features: FeatureThresholds = Field(default_factory=FeatureThresholds)
    trend: TrendThresholds = Field(default_factory=TrendThresholds)
    hysteresis: HysteresisConfig = Field(default_factory=HysteresisConfig)


default_thresholds = PredictionThresholdsConfig()

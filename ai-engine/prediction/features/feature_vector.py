"""
FeatureVector — Deterministic feature representation for risk scoring.

9 features, each with: raw value, normalized value, availability flag, unit.
All features explicitly track whether they are unavailable (not invalid).
Invalid inputs are rejected at the snapshot layer, not here.

Net inflow pressure is SIGNED — negative net flow is valid and preserved.
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class FeatureValue(BaseModel):
    """Single feature with full provenance tracking."""
    name: str
    raw_value: Optional[float] = Field(default=None, description="Pre-normalization value")
    normalized_value: float = Field(
        default=0.0,
        description="Value used in risk scoring. Signed for net_inflow_pressure; [0,1] for others."
    )
    feature_unavailable: bool = Field(
        default=False,
        description="True when feature cannot be computed (e.g. zero capacity). NOT for invalid inputs."
    )
    unavailable_reason: Optional[str] = Field(default=None)
    unit: str = Field(default="")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class FeatureVector(BaseModel):
    """Complete feature vector for one prediction evaluation (9 features)."""
    session_id: str
    venue_id: str
    timestamp: str

    # F1: occupancy / venue_capacity  [0, 2.0 clamped; unavail if capacity=0]
    occupancy_ratio: FeatureValue = Field(
        default_factory=lambda: FeatureValue(name="occupancy_ratio", unit="ratio")
    )
    # F2: entry_rate_5m / safe_entry_rate  [0, 3.0 clamped]
    entry_pressure: FeatureValue = Field(
        default_factory=lambda: FeatureValue(name="entry_pressure", unit="ratio")
    )
    # F3: exit_rate_5m / safe_exit_rate  [0, 3.0 clamped]
    exit_pressure: FeatureValue = Field(
        default_factory=lambda: FeatureValue(name="exit_pressure", unit="ratio")
    )
    # F4: net_flow_rate_5m / safe_net_flow_rate  SIGNED — negative preserved
    # Raw: signed ratio. Normalized: signed ratio.
    # Risk contribution: clamp(normalized, 0, 1) — only positive inflow contributes to risk.
    net_inflow_pressure: FeatureValue = Field(
        default_factory=lambda: FeatureValue(name="net_inflow_pressure", unit="signed_ratio")
    )
    # F5: density level mapped to [0.1, 1.0]
    density_score: FeatureValue = Field(
        default_factory=lambda: FeatureValue(name="density_score", unit="score_0_1")
    )
    # F6: congestion level mapped to [0.0, 1.0]
    congestion_score: FeatureValue = Field(
        default_factory=lambda: FeatureValue(name="congestion_score", unit="score_0_1")
    )
    # F7: weighted anomaly severity sum / max_score  [0, 1]
    anomaly_pressure: FeatureValue = Field(
        default_factory=lambda: FeatureValue(name="anomaly_pressure", unit="score_0_1")
    )
    # F8: (max_gate_rate - avg_gate_rate) / max(0.01, avg)  [0, inf)
    gate_imbalance: FeatureValue = Field(
        default_factory=lambda: FeatureValue(name="gate_imbalance", unit="ratio")
    )
    # F9: average_dwell / safe_dwell  [0, 3.0 clamped]
    dwell_pressure: FeatureValue = Field(
        default_factory=lambda: FeatureValue(name="dwell_pressure", unit="ratio")
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "venue_id": self.venue_id,
            "timestamp": self.timestamp,
            "features": {
                fv.name: fv.to_dict() for fv in [
                    self.occupancy_ratio, self.entry_pressure, self.exit_pressure,
                    self.net_inflow_pressure, self.density_score, self.congestion_score,
                    self.anomaly_pressure, self.gate_imbalance, self.dwell_pressure
                ]
            }
        }

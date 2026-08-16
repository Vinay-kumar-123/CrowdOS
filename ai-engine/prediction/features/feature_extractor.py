"""
FeatureExtractor — Deterministic feature extraction from PredictionInputSnapshot.

Produces FeatureVector. All 9 features are computed deterministically.

CRITICAL SEMANTICS (CTO mandated):
  - Negative occupancy/rates → rejected at snapshot layer (ValueError raised there)
  - Zero capacity            → occupancy_ratio.feature_unavailable = True (NOT an error)
  - Negative net flow        → PRESERVED as signed value through all layers
  - NaN/Infinity             → rejected at snapshot layer before reaching here

Net inflow pressure data flow:
  raw: net_flow_rate_5m / safe_net_flow_rate  (SIGNED)
  normalized_value: same signed value (preserved)
  risk contribution (in RiskScorer): clamp(normalized, 0.0, 1.0)
    → negative net flow contributes 0 to risk (risk-reducing, not risk-adding)
    → positive net flow contributes proportionally
  The signed raw value remains available for decision engine and trend analysis.
"""
from prediction.features.snapshot import PredictionInputSnapshot
from prediction.features.feature_vector import FeatureVector, FeatureValue
from prediction.features.normalization import (
    safe_ratio, clamp, map_density_level, map_congestion_level,
    compute_anomaly_pressure, compute_gate_imbalance
)
from prediction.config.thresholds import FeatureThresholds, default_thresholds


class FeatureExtractor:
    """
    Produces FeatureVector from PredictionInputSnapshot.
    Stateless — one instance can serve multiple concurrent calls safely
    (all state is local to each extract() call).
    """

    def __init__(self, thresholds: FeatureThresholds = None):
        self.thresholds = thresholds or default_thresholds.features

    def extract(self, snapshot: PredictionInputSnapshot) -> FeatureVector:
        """
        Extract all 9 features from snapshot.
        Returns FeatureVector. Does not raise for valid snapshots.
        """
        t = self.thresholds
        fv_fields = {
            "session_id": snapshot.session_id,
            "venue_id": snapshot.venue_id,
            "timestamp": snapshot.timestamp,
        }

        # ------------------------------------------------------------------
        # F1: Occupancy ratio = current_occupancy / venue_capacity
        # Zero capacity → feature_unavailable (NOT error — zero capacity is
        # a legitimate configuration state, e.g. capacity not yet configured)
        # ------------------------------------------------------------------
        if snapshot.venue_capacity == 0:
            fv_fields["occupancy_ratio"] = FeatureValue(
                name="occupancy_ratio",
                raw_value=None,
                normalized_value=0.0,
                feature_unavailable=True,
                unavailable_reason="venue_capacity is zero — cannot compute ratio",
                unit="ratio",
            )
        else:
            raw = snapshot.current_occupancy / snapshot.venue_capacity
            # Allow > 1.0 up to 2.0 to preserve over-capacity signal
            norm = clamp(raw, 0.0, 2.0)
            fv_fields["occupancy_ratio"] = FeatureValue(
                name="occupancy_ratio",
                raw_value=raw,
                normalized_value=norm,
                feature_unavailable=False,
                unit="ratio",
            )

        # ------------------------------------------------------------------
        # F2: Entry pressure = entry_rate_5m / safe_entry_rate  [0, 3.0]
        # entry_rate_5m is guaranteed >= 0 by snapshot validation
        # ------------------------------------------------------------------
        raw_ep = safe_ratio(
            snapshot.entry_rate_5m, t.safe_entry_rate_per_min,
            field_name="entry_pressure"
        )
        fv_fields["entry_pressure"] = FeatureValue(
            name="entry_pressure",
            raw_value=raw_ep,
            normalized_value=clamp(raw_ep, 0.0, 3.0),
            feature_unavailable=False,
            unit="ratio",
        )

        # ------------------------------------------------------------------
        # F3: Exit pressure = exit_rate_5m / safe_exit_rate  [0, 3.0]
        # ------------------------------------------------------------------
        raw_xp = safe_ratio(
            snapshot.exit_rate_5m, t.safe_exit_rate_per_min,
            field_name="exit_pressure"
        )
        fv_fields["exit_pressure"] = FeatureValue(
            name="exit_pressure",
            raw_value=raw_xp,
            normalized_value=clamp(raw_xp, 0.0, 3.0),
            feature_unavailable=False,
            unit="ratio",
        )

        # ------------------------------------------------------------------
        # F4: Net inflow pressure — SIGNED (negative net flow = outflow > inflow)
        # raw: net_flow_rate_5m / safe_net_flow_rate  (signed)
        # normalized_value: SIGNED preserved (negative IS valid)
        # risk contribution: clamp(normalized, 0.0, 1.0) [done in RiskScorer]
        # ------------------------------------------------------------------
        if t.safe_net_flow_rate_per_min <= 0.0:
            net_norm = 0.0
            net_unavail = True
            net_reason = "safe_net_flow_rate_per_min is zero or negative"
        else:
            net_norm = snapshot.net_flow_rate_5m / t.safe_net_flow_rate_per_min
            net_unavail = False
            net_reason = None
        fv_fields["net_inflow_pressure"] = FeatureValue(
            name="net_inflow_pressure",
            raw_value=net_norm,
            normalized_value=net_norm,  # SIGNED — preserved
            feature_unavailable=net_unavail,
            unavailable_reason=net_reason,
            unit="signed_ratio",
        )

        # ------------------------------------------------------------------
        # F5: Density score — deterministic level mapping [0.1, 1.0]
        # ------------------------------------------------------------------
        ds = map_density_level(snapshot.density_level)
        fv_fields["density_score"] = FeatureValue(
            name="density_score",
            raw_value=ds,
            normalized_value=ds,
            feature_unavailable=False,
            unit="score_0_1",
        )

        # ------------------------------------------------------------------
        # F6: Congestion score — deterministic level mapping [0.0, 1.0]
        # ------------------------------------------------------------------
        cs = map_congestion_level(snapshot.congestion_level)
        fv_fields["congestion_score"] = FeatureValue(
            name="congestion_score",
            raw_value=cs,
            normalized_value=cs,
            feature_unavailable=False,
            unit="score_0_1",
        )

        # ------------------------------------------------------------------
        # F7: Anomaly pressure [0.0, 1.0]
        # Severity weights: INFO=0.1, LOW=0.2, MEDIUM=0.5, HIGH=0.8, CRITICAL=1.0
        # Anomalies counted per gate independently
        # ------------------------------------------------------------------
        ap = compute_anomaly_pressure(
            snapshot.active_anomalies,
            max_score=t.max_anomaly_score,
        )
        fv_fields["anomaly_pressure"] = FeatureValue(
            name="anomaly_pressure",
            raw_value=ap,
            normalized_value=ap,
            feature_unavailable=False,
            unit="score_0_1",
        )

        # ------------------------------------------------------------------
        # F8: Gate imbalance — uses per-gate entry_rate_5m [0, inf)
        # Single gate → 0.0 (not unavailable, physically correct)
        # No gates → feature_unavailable=True
        # ------------------------------------------------------------------
        gate_rates = [gs.entry_rate_5m for gs in snapshot.gate_snapshots.values()]
        gi = compute_gate_imbalance(gate_rates)
        has_gates = len(snapshot.gate_snapshots) > 0
        fv_fields["gate_imbalance"] = FeatureValue(
            name="gate_imbalance",
            raw_value=gi,
            normalized_value=gi,
            feature_unavailable=not has_gates,
            unavailable_reason="no gate snapshots provided" if not has_gates else None,
            unit="ratio",
        )

        # ------------------------------------------------------------------
        # F9: Dwell pressure = average_dwell / safe_dwell  [0, 3.0]
        # ------------------------------------------------------------------
        dp = safe_ratio(
            snapshot.average_dwell, t.safe_dwell_seconds,
            field_name="dwell_pressure"
        )
        fv_fields["dwell_pressure"] = FeatureValue(
            name="dwell_pressure",
            raw_value=dp,
            normalized_value=clamp(dp, 0.0, 3.0),
            feature_unavailable=False,
            unit="ratio",
        )

        return FeatureVector(**fv_fields)

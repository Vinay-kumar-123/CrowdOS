"""
PredictionInputSnapshot — Immutable, privacy-safe DTO for Sprint 8.

This is the authoritative input contract. It captures Sprint 7 outputs as
primitive scalars. It contains NO raw images, NO embeddings, NO biometric
vectors, NO face crops, NO unnecessary identity data.

INVALID INPUT SEMANTICS (CTO constraint):
  - Negative occupancy        → ValueError("INVALID_INPUT: ...")
  - Negative entry/exit rate  → ValueError("INVALID_INPUT: ...")
  - Negative capacity         → ValueError("INVALID_CONFIGURATION: ...")
  - NaN in any numeric field  → ValueError("INVALID_INPUT: ...")
  - Infinity in any field     → ValueError("INVALID_INPUT: ...")
  - Zero capacity             → Allowed: feature_unavailable=True (not an error)
  - Negative net flow         → Allowed: physically valid (exits > entries)
"""
import math
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_non_negative_int(name: str, value: int) -> None:
    """Integer must be >= 0. Negative is INVALID_INPUT."""
    if value < 0:
        raise ValueError(f"INVALID_INPUT: {name} cannot be negative, got {value}")


def _validate_rate(name: str, value: float) -> None:
    """Entry/exit rates must be non-negative and finite."""
    if math.isnan(value):
        raise ValueError(f"INVALID_INPUT: {name} is NaN")
    if math.isinf(value):
        raise ValueError(f"INVALID_INPUT: {name} is Infinity")
    if value < 0.0:
        raise ValueError(f"INVALID_INPUT: {name} cannot be negative, got {value}")


def _validate_finite(name: str, value: float) -> None:
    """Value must be finite; negative IS allowed (e.g. net flow)."""
    if math.isnan(value):
        raise ValueError(f"INVALID_INPUT: {name} is NaN")
    if math.isinf(value):
        raise ValueError(f"INVALID_INPUT: {name} is Infinity")


# ---------------------------------------------------------------------------
# Gate-level snapshot
# ---------------------------------------------------------------------------

class GateInputSnapshot(BaseModel):
    """
    Gate-level metrics snapshot derived from Sprint 7 FlowMetrics.
    Validation rules:
      entry_rate_5m, exit_rate_5m, entry_rate_1m >= 0 (rates cannot be negative)
      net_flow_rate_5m may be negative (exits > entries)
      gate_occupancy, cumulative counts >= 0
    """
    gate_id: str
    entry_rate_5m: float = Field(default=0.0)
    exit_rate_5m: float = Field(default=0.0)
    net_flow_rate_5m: float = Field(default=0.0)
    entry_rate_1m: float = Field(default=0.0)
    cumulative_entries: int = Field(default=0)
    cumulative_exits: int = Field(default=0)
    gate_occupancy: int = Field(default=0)
    is_active: bool = Field(default=True)

    @model_validator(mode="after")
    def validate_gate_fields(self):
        _validate_non_negative_int("gate_occupancy", self.gate_occupancy)
        _validate_non_negative_int("cumulative_entries", self.cumulative_entries)
        _validate_non_negative_int("cumulative_exits", self.cumulative_exits)
        _validate_rate("entry_rate_5m", self.entry_rate_5m)
        _validate_rate("exit_rate_5m", self.exit_rate_5m)
        _validate_finite("net_flow_rate_5m", self.net_flow_rate_5m)  # signed
        _validate_rate("entry_rate_1m", self.entry_rate_1m)
        return self


# ---------------------------------------------------------------------------
# Venue-level snapshot
# ---------------------------------------------------------------------------

class PredictionInputSnapshot(BaseModel):
    """
    Immutable input snapshot for Sprint 8 Prediction Engine.

    Privacy guarantee: NO embeddings, NO biometric vectors, NO face crops,
    NO raw images, NO identity tokens. Only aggregated operational metrics.

    Consumed from Sprint 7 interfaces:
      - FlowMetrics   → entry_rate_*, exit_rate_*, net_flow_rate_*
      - OccupancyAnalyticsSummary → current_occupancy, gate_occupancy, busiest_gate
      - DensityState  → density_level, congestion_level, occupancy_ratio
      - DwellMetrics  → average_dwell, p95_dwell
      - AnomalySignal → active_anomalies (type + severity strings only)
      - AlertManager  → active_alert_count
    """

    # Identity / session context
    session_id: str = Field(...)
    venue_id: str = Field(...)
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    session_status: str = Field(default="ACTIVE", description="SessionStatus string value")

    # Capacity (configured externally — Sprint 7 does not store this)
    venue_capacity: int = Field(default=1000, description="Configured maximum venue capacity")

    # Venue-level occupancy (from Sprint 7 OccupancyAnalyticsSummary)
    current_occupancy: int = Field(default=0)
    total_entries: int = Field(default=0)
    total_exits: int = Field(default=0)
    busiest_gate: Optional[str] = Field(default=None)
    gate_occupancy: Dict[str, int] = Field(default_factory=dict)

    # Venue-level flow (from Sprint 7 FlowMetrics)
    entry_rate_1m: float = Field(default=0.0, description="Entry rate persons/min (1m window)")
    entry_rate_5m: float = Field(default=0.0, description="Entry rate persons/min (5m window)")
    exit_rate_5m: float = Field(default=0.0, description="Exit rate persons/min (5m window)")
    net_flow_rate_5m: float = Field(default=0.0, description="Net flow persons/min (5m) — SIGNED")
    entry_rate_15m: float = Field(default=0.0, description="Entry rate persons/min (15m window)")

    # Density/congestion (from Sprint 7 DensityState)
    density_level: str = Field(default="LOW", description="CrowdDensityLevel value string")
    congestion_level: str = Field(default="NORMAL", description="CongestionLevel value string")
    occupancy_ratio: float = Field(default=0.0, description="Occupancy/high_max ratio from Sprint 7")

    # Gate-level snapshots (keyed by gate_id)
    gate_snapshots: Dict[str, GateInputSnapshot] = Field(default_factory=dict)

    # Anomaly signals — type and severity strings ONLY. No biometric metadata.
    active_anomalies: List[Dict[str, str]] = Field(
        default_factory=list,
        description=(
            "List of {anomaly_type, severity, gate_id} dicts. "
            "Anomalies counted per gate independently. No biometric fields."
        )
    )

    # Alert state (from Sprint 7 AlertManager)
    active_alert_count: int = Field(default=0)

    # Dwell (from Sprint 7 DwellMetrics)
    average_dwell: float = Field(default=0.0, description="Average dwell time seconds")
    p95_dwell: float = Field(default=0.0, description="P95 dwell time seconds")

    model_config = {"frozen": True}  # Immutable after construction

    @model_validator(mode="after")
    def validate_snapshot(self):
        # Capacity validation
        if self.venue_capacity < 0:
            raise ValueError(
                f"INVALID_CONFIGURATION: venue_capacity cannot be negative, got {self.venue_capacity}"
            )
        # Occupancy / counts — must be non-negative
        _validate_non_negative_int("current_occupancy", self.current_occupancy)
        _validate_non_negative_int("total_entries", self.total_entries)
        _validate_non_negative_int("total_exits", self.total_exits)
        _validate_non_negative_int("active_alert_count", self.active_alert_count)

        # Entry/exit rates — non-negative and finite
        for field_name in ("entry_rate_1m", "entry_rate_5m", "exit_rate_5m", "entry_rate_15m"):
            _validate_rate(field_name, getattr(self, field_name))

        # Net flow — signed but must be finite (NaN/Inf rejected)
        _validate_finite("net_flow_rate_5m", self.net_flow_rate_5m)

        # Dwell — non-negative and finite
        _validate_rate("average_dwell", self.average_dwell)
        _validate_rate("p95_dwell", self.p95_dwell)

        # occupancy_ratio — finite (may exceed 1.0 when over capacity)
        _validate_finite("occupancy_ratio", self.occupancy_ratio)

        return self

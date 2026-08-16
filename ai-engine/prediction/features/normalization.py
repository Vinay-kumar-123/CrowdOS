"""
Deterministic Normalization Utilities for Sprint 8.

Rules:
  - No NaN propagation
  - No Infinity propagation
  - Safe zero-denominator handling (returns 0.0)
  - Invalid inputs (NaN/Inf) raise ValueError — they are NOT silently zeroed
  - Negative net flow preserved through normalization (NOT clamped here)
  - Clamping happens only at the risk scoring contribution layer

Anomaly pressure definition:
  Severity weights: INFO=0.1, LOW=0.2, MEDIUM=0.5, HIGH=0.8, CRITICAL=1.0
  Count anomalies per gate independently (same type at different gates counts separately)
  max_possible_score = configurable denominator (default 5.0)
  anomaly_pressure = clamp(sum_of_weights / max_score, 0.0, 1.0)

Gate imbalance definition:
  Uses per-gate entry_rate_5m (NOT occupancy)
  Inactive gates (rate=0.0): included as 0.0 in average
  Missing gates: excluded
  Single gate: imbalance = 0.0 (not unavailable, just zero)
  Formula: (max_rate - avg_rate) / max(0.01, avg_rate)
  HIGH imbalance threshold: gate_imbalance >= high_imbalance_threshold (default 2.0)
"""
import math
from typing import List


# ---------------------------------------------------------------------------
# Core safe-math utilities
# ---------------------------------------------------------------------------

def safe_ratio(numerator: float, denominator: float, *, field_name: str = "ratio") -> float:
    """
    numerator / denominator with zero-denominator guard.
    Raises ValueError if either value is NaN or Infinity.
    Returns 0.0 if denominator is zero or negative.
    """
    if math.isnan(numerator) or math.isinf(numerator):
        raise ValueError(f"INVALID_INPUT: {field_name} numerator is NaN/Infinity")
    if math.isnan(denominator) or math.isinf(denominator):
        raise ValueError(f"INVALID_INPUT: {field_name} denominator is NaN/Infinity")
    if denominator <= 0.0:
        return 0.0
    return numerator / denominator


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp value to [min_val, max_val]. Returns min_val for NaN."""
    if math.isnan(value):
        return min_val
    return max(min_val, min(max_val, value))


# ---------------------------------------------------------------------------
# Deterministic level mappings
# ---------------------------------------------------------------------------

_DENSITY_MAP = {
    "LOW": 0.1,
    "MODERATE": 0.4,
    "HIGH": 0.75,
    "CRITICAL": 1.0,
}

_CONGESTION_MAP = {
    "NORMAL": 0.0,
    "BUILDING": 0.33,
    "CONGESTED": 0.67,
    "SEVERE_CONGESTION": 1.0,
}

_SEVERITY_WEIGHTS = {
    "INFO": 0.1,
    "LOW": 0.2,
    "MEDIUM": 0.5,
    "HIGH": 0.8,
    "CRITICAL": 1.0,
}


def map_density_level(density_level_str: str) -> float:
    """Deterministic numeric mapping for CrowdDensityLevel. Defaults to LOW (0.1)."""
    return _DENSITY_MAP.get(density_level_str.upper().strip(), 0.1)


def map_congestion_level(congestion_level_str: str) -> float:
    """Deterministic numeric mapping for CongestionLevel. Defaults to NORMAL (0.0)."""
    return _CONGESTION_MAP.get(congestion_level_str.upper().strip(), 0.0)


# ---------------------------------------------------------------------------
# Anomaly pressure
# ---------------------------------------------------------------------------

def compute_anomaly_pressure(anomalies: list, max_score: float = 5.0) -> float:
    """
    Compute deterministic anomaly pressure in [0.0, 1.0].

    Definition:
      - anomalies: list of dicts with 'severity' key (and optionally 'gate_id')
      - Severity weights: INFO=0.1, LOW=0.2, MEDIUM=0.5, HIGH=0.8, CRITICAL=1.0
      - Anomalies counted PER GATE independently (same type at gate_A and gate_B = 2 counts)
      - max_score: normalization denominator (default 5.0)
      - Result clamped to [0.0, 1.0]

    Returns 0.0 if no anomalies. Never raises.
    """
    if not anomalies or max_score <= 0.0:
        return 0.0
    total_weight = 0.0
    for a in anomalies:
        sev = str(a.get("severity", "MEDIUM")).upper().strip()
        total_weight += _SEVERITY_WEIGHTS.get(sev, 0.5)
    return clamp(total_weight / max_score, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Gate imbalance
# ---------------------------------------------------------------------------

def compute_gate_imbalance(gate_rates: List[float]) -> float:
    """
    Compute gate flow imbalance from a list of per-gate entry_rate_5m values.

    Definition:
      - Uses entry_rate_5m (NOT gate_occupancy)
      - Inactive gates (rate=0.0): included as 0.0 in average calculation
      - Missing gates: excluded (not passed in the list)
      - Single gate: returns 0.0
      - Formula: (max_rate - avg_rate) / max(0.01, avg_rate)
      - Returns float >= 0.0

    HIGH imbalance is detected by the caller comparing to high_imbalance_threshold.
    """
    if not gate_rates:
        return 0.0
    if len(gate_rates) == 1:
        return 0.0
    n = len(gate_rates)
    avg = sum(gate_rates) / n
    max_rate = max(gate_rates)
    return (max_rate - avg) / max(0.01, avg)

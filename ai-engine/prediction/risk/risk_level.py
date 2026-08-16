"""
RiskLevel enumeration for CrowdOS Sprint 8.

Score ranges (configurable via RiskLevelThresholds):
  0-19:   LOW
  20-39:  GUARDED
  40-59:  ELEVATED
  60-79:  HIGH
  80-100: CRITICAL
"""
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "LOW"           # Score 0-19
    GUARDED = "GUARDED"   # Score 20-39
    ELEVATED = "ELEVATED" # Score 40-59
    HIGH = "HIGH"         # Score 60-79
    CRITICAL = "CRITICAL" # Score 80-100


RISK_LEVEL_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.GUARDED: 1,
    RiskLevel.ELEVATED: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}


def score_to_risk_level(score: float, thresholds=None) -> RiskLevel:
    """
    Map a numeric risk score [0, 100] to RiskLevel.
    Uses configurable thresholds. Defaults: 20/40/60/80.
    """
    from prediction.config.thresholds import RiskLevelThresholds
    t = thresholds or RiskLevelThresholds()
    if score >= t.critical_min:
        return RiskLevel.CRITICAL
    elif score >= t.high_min:
        return RiskLevel.HIGH
    elif score >= t.elevated_min:
        return RiskLevel.ELEVATED
    elif score >= t.guarded_min:
        return RiskLevel.GUARDED
    return RiskLevel.LOW

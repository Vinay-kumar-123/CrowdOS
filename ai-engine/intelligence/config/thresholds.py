"""
Configuration and Threshold Schemas for Crowd Density & Congestion Detection.
"""
from enum import Enum
from typing import Dict, Any
from pydantic import BaseModel, Field, model_validator


class CrowdDensityLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CongestionLevel(str, Enum):
    NORMAL = "NORMAL"
    BUILDING = "BUILDING"
    CONGESTED = "CONGESTED"
    SEVERE_CONGESTION = "SEVERE_CONGESTION"


class CrowdThresholdConfig(BaseModel):
    """
    Configurable Venue Crowd Density Thresholds.
    Logical order required: 0 <= low_max < moderate_max < high_max < critical_min
    """
    low_max: int = Field(default=50, description="Max occupancy for LOW density level")
    moderate_max: int = Field(default=150, description="Max occupancy for MODERATE density level")
    high_max: int = Field(default=300, description="Max occupancy for HIGH density level")
    critical_min: int = Field(default=301, description="Min occupancy for CRITICAL density level")

    @model_validator(mode="after")
    def validate_threshold_order(self):
        if self.low_max < 0:
            raise ValueError(f"low_max must be >= 0, got {self.low_max}")
        if not (self.low_max < self.moderate_max < self.high_max < self.critical_min):
            raise ValueError(
                f"Invalid threshold order: low_max ({self.low_max}) < moderate_max ({self.moderate_max}) "
                f"< high_max ({self.high_max}) < critical_min ({self.critical_min}) required."
            )
        return self

    def classify_occupancy(self, occupancy: int) -> CrowdDensityLevel:
        """Classify occupancy into LOW, MODERATE, HIGH, or CRITICAL."""
        if occupancy <= self.low_max:
            return CrowdDensityLevel.LOW
        elif occupancy <= self.moderate_max:
            return CrowdDensityLevel.MODERATE
        elif occupancy <= self.high_max:
            return CrowdDensityLevel.HIGH
        else:
            return CrowdDensityLevel.CRITICAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "low_max": self.low_max,
            "moderate_max": self.moderate_max,
            "high_max": self.high_max,
            "critical_min": self.critical_min
        }


class CongestionThresholdConfig(BaseModel):
    """
    Rule-based Congestion Detection Thresholds with Hysteresis.
    """
    building_ratio: float = Field(default=0.60, description="Ratio of high_max to enter BUILDING congestion")
    congested_ratio: float = Field(default=0.85, description="Ratio of high_max to enter CONGESTED level")
    severe_ratio: float = Field(default=1.00, description="Ratio of high_max to enter SEVERE_CONGESTION level")

    # Flow thresholds (people per minute)
    surge_entry_rate: float = Field(default=20.0, description="Entry rate triggering ENTRY_SURGE anomaly")
    surge_exit_rate: float = Field(default=20.0, description="Exit rate triggering EXIT_SURGE anomaly")

    # Hysteresis recovery margins (e.g. 5% reduction required to downgrade congestion level)
    hysteresis_margin: float = Field(default=0.05, description="Hysteresis buffer fraction preventing alert flapping")

"""
Trend state enumerations and TrendResult model for Sprint 8.
"""
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class TrendDirection(str, Enum):
    INCREASING = "INCREASING"
    STABLE = "STABLE"
    DECREASING = "DECREASING"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class TrendStrength(str, Enum):
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    UNKNOWN = "UNKNOWN"  # Only when INSUFFICIENT_DATA


class TrendResult(BaseModel):
    """Result of trend detection over bounded historical risk scores."""
    session_id: str
    venue_id: str
    timestamp: str
    direction: TrendDirection = Field(default=TrendDirection.INSUFFICIENT_DATA)
    strength: TrendStrength = Field(default=TrendStrength.UNKNOWN)
    slope: Optional[float] = Field(default=None, description="Risk score change per minute (Theil-Sen)")
    n_observations: int = Field(default=0)
    time_span_seconds: float = Field(default=0.0)
    message: str = Field(default="")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "venue_id": self.venue_id,
            "timestamp": self.timestamp,
            "direction": self.direction.value,
            "strength": self.strength.value,
            "slope": round(self.slope, 4) if self.slope is not None else None,
            "n_observations": self.n_observations,
            "time_span_seconds": round(self.time_span_seconds, 1),
            "message": self.message,
        }

"""
Density & Congestion Analytics Engine.
Evaluates CrowdDensityLevel (LOW, MODERATE, HIGH, CRITICAL) and
CongestionLevel (NORMAL, BUILDING, CONGESTED, SEVERE_CONGESTION)
using configurable thresholds and hysteresis to prevent alert flapping.
"""
import threading
from typing import Dict, Any, Tuple
from pydantic import BaseModel, Field
from intelligence.config.thresholds import (
    CrowdThresholdConfig, CongestionThresholdConfig, CrowdDensityLevel, CongestionLevel
)


class DensityState(BaseModel):
    venue_id: str = Field(default="default_venue")
    occupancy: int = Field(default=0)
    density_level: CrowdDensityLevel = Field(default=CrowdDensityLevel.LOW)
    congestion_level: CongestionLevel = Field(default=CongestionLevel.NORMAL)
    occupancy_ratio: float = Field(default=0.0, description="Ratio of current occupancy to high_max threshold")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "venue_id": self.venue_id,
            "occupancy": self.occupancy,
            "density_level": self.density_level.value if isinstance(self.density_level, CrowdDensityLevel) else str(self.density_level),
            "congestion_level": self.congestion_level.value if isinstance(self.congestion_level, CongestionLevel) else str(self.congestion_level),
            "occupancy_ratio": round(self.occupancy_ratio, 4),
        }


class DensityAnalytics:
    """
    Thread-safe Crowd Density and Congestion Analytics Engine.
    """

    def __init__(
        self,
        crowd_config: Optional[CrowdThresholdConfig] = None,
        congestion_config: Optional[CongestionThresholdConfig] = None,
        venue_id: str = "default_venue"
    ):
        self.venue_id = venue_id
        self.crowd_config = crowd_config or CrowdThresholdConfig()
        self.congestion_config = congestion_config or CongestionThresholdConfig()
        self._current_congestion = CongestionLevel.NORMAL
        self._lock = threading.Lock()

    def evaluate(
        self,
        occupancy: int,
        net_flow_rate_5m: float = 0.0
    ) -> DensityState:
        """
        Evaluate density level and congestion level from current occupancy and 5m net flow rate.
        Enforces hysteresis to prevent alert flapping near threshold boundaries.
        """
        with self._lock:
            # 1. Density Level
            density_lvl = self.crowd_config.classify_occupancy(occupancy)

            # 2. Occupancy Ratio against high_max
            high_max = max(1, self.crowd_config.high_max)
            ratio = occupancy / high_max

            # 3. Rule-based Congestion Level with Hysteresis
            h_margin = self.congestion_config.hysteresis_margin
            b_ratio = self.congestion_config.building_ratio
            c_ratio = self.congestion_config.congested_ratio
            s_ratio = self.congestion_config.severe_ratio

            target_congestion = CongestionLevel.NORMAL

            if ratio >= s_ratio or (ratio >= c_ratio and net_flow_rate_5m > 10.0):
                target_congestion = CongestionLevel.SEVERE_CONGESTION
            elif ratio >= c_ratio or (ratio >= b_ratio and net_flow_rate_5m > 5.0):
                target_congestion = CongestionLevel.CONGESTED
            elif ratio >= b_ratio or net_flow_rate_5m > 15.0:
                target_congestion = CongestionLevel.BUILDING
            else:
                target_congestion = CongestionLevel.NORMAL

            # Apply Hysteresis for downgrades
            if self._is_downgrade(target_congestion, self._current_congestion):
                # Check if ratio has dropped sufficiently below lower threshold
                if self._current_congestion == CongestionLevel.SEVERE_CONGESTION and ratio > (s_ratio - h_margin):
                    target_congestion = CongestionLevel.SEVERE_CONGESTION
                elif self._current_congestion == CongestionLevel.CONGESTED and ratio > (c_ratio - h_margin):
                    target_congestion = CongestionLevel.CONGESTED
                elif self._current_congestion == CongestionLevel.BUILDING and ratio > (b_ratio - h_margin):
                    target_congestion = CongestionLevel.BUILDING

            self._current_congestion = target_congestion

            return DensityState(
                venue_id=self.venue_id,
                occupancy=occupancy,
                density_level=density_lvl,
                congestion_level=self._current_congestion,
                occupancy_ratio=ratio
            )

    def _is_downgrade(self, new_level: CongestionLevel, current_level: CongestionLevel) -> bool:
        order = {
            CongestionLevel.NORMAL: 0,
            CongestionLevel.BUILDING: 1,
            CongestionLevel.CONGESTED: 2,
            CongestionLevel.SEVERE_CONGESTION: 3
        }
        return order.get(new_level, 0) < order.get(current_level, 0)

    def reset() -> None:
        with self._lock:
            self._current_congestion = CongestionLevel.NORMAL

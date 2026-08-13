"""
Peak Analytics Tracker.
Tracks peak occupancy, peak entry rate, peak exit rate, and peak congestion level
along with their exact ISO timestamps.
Enforces deterministic tie-breaking (first occurrence preserved).
"""
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from intelligence.config.thresholds import CongestionLevel


class PeakMetrics(BaseModel):
    venue_id: str = Field(default="default_venue")
    peak_occupancy: int = Field(default=0)
    peak_occupancy_timestamp: Optional[str] = Field(default=None)

    peak_entry_rate: float = Field(default=0.0)
    peak_entry_rate_timestamp: Optional[str] = Field(default=None)

    peak_exit_rate: float = Field(default=0.0)
    peak_exit_rate_timestamp: Optional[str] = Field(default=None)

    peak_congestion_level: CongestionLevel = Field(default=CongestionLevel.NORMAL)
    peak_congestion_timestamp: Optional[str] = Field(default=None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "venue_id": self.venue_id,
            "peak_occupancy": self.peak_occupancy,
            "peak_occupancy_timestamp": self.peak_occupancy_timestamp,
            "peak_entry_rate": self.peak_entry_rate,
            "peak_entry_rate_timestamp": self.peak_entry_rate_timestamp,
            "peak_exit_rate": self.peak_exit_rate,
            "peak_exit_rate_timestamp": self.peak_exit_rate_timestamp,
            "peak_congestion_level": self.peak_congestion_level.value if isinstance(self.peak_congestion_level, CongestionLevel) else str(self.peak_congestion_level),
            "peak_congestion_timestamp": self.peak_congestion_timestamp,
        }


class PeakTracker:
    """
    Thread-safe Peak Analytics Tracker.
    """

    def __init__(self, venue_id: str = "default_venue"):
        self.venue_id = venue_id
        self._peak_occupancy = 0
        self._peak_occupancy_ts: Optional[str] = None

        self._peak_entry_rate = 0.0
        self._peak_entry_rate_ts: Optional[str] = None

        self._peak_exit_rate = 0.0
        self._peak_exit_rate_ts: Optional[str] = None

        self._peak_congestion = CongestionLevel.NORMAL
        self._peak_congestion_ts: Optional[str] = None

        self._lock = threading.Lock()

    def update_occupancy(self, occupancy: int, timestamp: Optional[str] = None) -> bool:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        with self._lock:
            # Strictly greater than -> preserves earlier peak timestamp on tie
            if occupancy > self._peak_occupancy:
                self._peak_occupancy = occupancy
                self._peak_occupancy_ts = ts
                return True
        return False

    def update_entry_rate(self, rate: float, timestamp: Optional[str] = None) -> bool:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        with self._lock:
            if rate > self._peak_entry_rate:
                self._peak_entry_rate = round(rate, 2)
                self._peak_entry_rate_ts = ts
                return True
        return False

    def update_exit_rate(self, rate: float, timestamp: Optional[str] = None) -> bool:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        with self._lock:
            if rate > self._peak_exit_rate:
                self._peak_exit_rate = round(rate, 2)
                self._peak_exit_rate_ts = ts
                return True
        return False

    def update_congestion(self, level: CongestionLevel, timestamp: Optional[str] = None) -> bool:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        order = {
            CongestionLevel.NORMAL: 0,
            CongestionLevel.BUILDING: 1,
            CongestionLevel.CONGESTED: 2,
            CongestionLevel.SEVERE_CONGESTION: 3
        }
        with self._lock:
            if order.get(level, 0) > order.get(self._peak_congestion, 0):
                self._peak_congestion = level
                self._peak_congestion_ts = ts
                return True
        return False

    def get_peaks(self) -> PeakMetrics:
        with self._lock:
            return PeakMetrics(
                venue_id=self.venue_id,
                peak_occupancy=self._peak_occupancy,
                peak_occupancy_timestamp=self._peak_occupancy_ts,
                peak_entry_rate=self._peak_entry_rate,
                peak_entry_rate_timestamp=self._peak_entry_rate_ts,
                peak_exit_rate=self._peak_exit_rate,
                peak_exit_rate_timestamp=self._peak_exit_rate_ts,
                peak_congestion_level=self._peak_congestion,
                peak_congestion_timestamp=self._peak_congestion_ts
            )

    def reset(self) -> None:
        with self._lock:
            self._peak_occupancy = 0
            self._peak_occupancy_ts = None
            self._peak_entry_rate = 0.0
            self._peak_entry_rate_ts = None
            self._peak_exit_rate = 0.0
            self._peak_exit_rate_ts = None
            self._peak_congestion = CongestionLevel.NORMAL
            self._peak_congestion_ts = None

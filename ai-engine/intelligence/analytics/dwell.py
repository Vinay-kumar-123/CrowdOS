"""
Aggregate Dwell Time Analytics Module.
Calculates average, median, minimum, maximum, and P95 dwell times.
Handles empty streams, None, zero, negative/invalid dwell values safely.
Uses deterministic nearest-rank method for P95 percentile.
"""
import math
import threading
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class DwellMetrics(BaseModel):
    total_samples: int = Field(default=0)
    average_dwell: float = Field(default=0.0)
    median_dwell: float = Field(default=0.0)
    min_dwell: float = Field(default=0.0)
    max_dwell: float = Field(default=0.0)
    p95_dwell: float = Field(default=0.0)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


def calculate_p95_nearest_rank(sorted_values: List[float]) -> float:
    """
    Deterministic P95 calculation using nearest-rank method.
    Index = ceil(0.95 * N) - 1.
    """
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    rank = math.ceil(0.95 * n) - 1
    rank = max(0, min(n - 1, rank))
    return round(float(sorted_values[rank]), 2)


class DwellAnalytics:
    """
    Thread-safe Dwell Time Aggregator.
    """

    def __init__(self, max_samples: int = 10000):
        self.max_samples = max_samples
        self._dwell_samples: List[float] = []
        self._lock = threading.Lock()

    def record_dwell(self, dwell_seconds: Optional[float]) -> bool:
        """
        Record a dwell time sample. Ignores None, NaN, and negative values.
        """
        if dwell_seconds is None:
            return False

        try:
            val = float(dwell_seconds)
            if math.isnan(val) or math.isinf(val) or val < 0.0:
                return False
        except (ValueError, TypeError):
            return False

        with self._lock:
            self._dwell_samples.append(val)
            if len(self._dwell_samples) > self.max_samples:
                self._dwell_samples.pop(0)
        return True

    def get_metrics(self) -> DwellMetrics:
        with self._lock:
            if not self._dwell_samples:
                return DwellMetrics()

            clean = sorted(self._dwell_samples)
            n = len(clean)
            avg_d = sum(clean) / n
            min_d = clean[0]
            max_d = clean[-1]

            # Median
            if n % 2 == 1:
                median_d = clean[n // 2]
            else:
                median_d = (clean[(n // 2) - 1] + clean[n // 2]) / 2.0

            p95_d = calculate_p95_nearest_rank(clean)

            return DwellMetrics(
                total_samples=n,
                average_dwell=round(avg_d, 2),
                median_dwell=round(median_d, 2),
                min_dwell=round(min_d, 2),
                max_dwell=round(max_d, 2),
                p95_dwell=p95_d
            )

    def reset(self) -> None:
        with self._lock:
            self._dwell_samples.clear()

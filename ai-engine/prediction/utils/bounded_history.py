"""
BoundedObservationHistory — Thread-safe bounded observation buffer.

Stores (timestamp_epoch, value) pairs.
Enforces:
  - max_observations: maximum number of stored items (oldest evicted)
  - max_age_seconds: items older than this are evicted on add()
Thread-safe via threading.Lock.
"""
import threading
from collections import deque
from typing import List, Tuple


class BoundedObservationHistory:
    """Thread-safe bounded observation buffer with age-based eviction."""

    def __init__(
        self,
        max_observations: int = 1000,
        max_age_seconds: float = 3600.0,
    ):
        if max_observations < 1:
            raise ValueError(f"max_observations must be >= 1, got {max_observations}")
        self.max_observations = max_observations
        self.max_age_seconds = max_age_seconds
        self._data: deque = deque()
        self._lock = threading.Lock()

    def add(self, timestamp_epoch: float, value: float) -> None:
        """Add observation. Evicts stale/excess items."""
        with self._lock:
            self._data.append((timestamp_epoch, value))
            self._evict_unlocked(timestamp_epoch)

    def _evict_unlocked(self, current_epoch: float) -> None:
        """Evict by age first, then by max capacity."""
        cutoff = current_epoch - self.max_age_seconds
        while self._data and self._data[0][0] < cutoff:
            self._data.popleft()
        while len(self._data) > self.max_observations:
            self._data.popleft()

    def get_all(self) -> List[Tuple[float, float]]:
        """Return all observations as (epoch_ts, value) list."""
        with self._lock:
            return list(self._data)

    def get_recent(self, n: int) -> List[Tuple[float, float]]:
        """Return the most recent n observations."""
        with self._lock:
            data = list(self._data)
        return data[-n:] if len(data) > n else data

    def size(self) -> int:
        with self._lock:
            return len(self._data)

    def reset(self) -> None:
        with self._lock:
            self._data.clear()

"""
Thread-safe Bounded Time Window Data Structure.
Maintains timestamped data points within a sliding time window (e.g. 60s, 300s, 900s, 3600s).
Enforces max item capacity bounds to prevent unbounded memory growth during continuous operations.
"""
import time
import threading
from collections import deque
from datetime import datetime, timezone
from typing import List, Tuple, Any, Optional


def parse_timestamp_epoch(ts: str) -> float:
    """Parse ISO timestamp or fallback to current epoch time."""
    if not ts:
        return time.time()
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return time.time()


class BoundedTimeWindow:
    """
    Thread-safe sliding time window.
    Stores tuples of (epoch_timestamp, value).
    """

    def __init__(self, window_seconds: float = 60.0, max_capacity: int = 10000):
        self.window_seconds = float(window_seconds)
        self.max_capacity = max_capacity
        self._data: deque = deque()
        self._lock = threading.Lock()

    def add(self, value: Any, timestamp: Optional[str] = None) -> None:
        epoch_ts = parse_timestamp_epoch(timestamp) if timestamp else time.time()
        with self._lock:
            self._data.append((epoch_ts, value))
            self._evict_expired_unlocked(epoch_ts)

    def _evict_expired_unlocked(self, current_epoch: float) -> None:
        cutoff = current_epoch - self.window_seconds
        # Remove items older than window
        while self._data and self._data[0][0] < cutoff:
            self._data.popleft()
        # Cap max capacity if exceeded
        while len(self._data) > self.max_capacity:
            self._data.popleft()

    def cleanup(self, current_time: Optional[float] = None) -> None:
        now = current_time if current_time is not None else time.time()
        with self._lock:
            self._evict_expired_unlocked(now)

    def get_values(self, current_time: Optional[float] = None) -> List[Any]:
        now = current_time if current_time is not None else time.time()
        with self._lock:
            self._evict_expired_unlocked(now)
            return [val for _, val in self._data]

    def count(self, current_time: Optional[float] = None) -> int:
        now = current_time if current_time is not None else time.time()
        with self._lock:
            self._evict_expired_unlocked(now)
            return len(self._data)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

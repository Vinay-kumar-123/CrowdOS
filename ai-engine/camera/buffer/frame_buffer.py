import threading
from collections import deque
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import numpy as np


class FrameItem:
    def __init__(self, frame: np.ndarray, frame_number: int, timestamp: Optional[float] = None):
        self.frame = frame
        self.frame_number = frame_number
        self.timestamp = timestamp or datetime.now(timezone.utc).timestamp()


class FrameBuffer:
    """
    Thread-safe FIFO Ring-Buffer for video frame storage with zero-copy reference handing.
    """
    def __init__(self, max_size: int = 30):
        self.max_size = max_size
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.Lock()
        self.dropped_count = 0

    def push(self, frame: np.ndarray, frame_number: int, timestamp: Optional[float] = None) -> bool:
        """
        Push a frame into the FIFO buffer. Overwrites oldest frame if buffer is full.
        """
        with self.lock:
            if len(self.buffer) == self.max_size:
                self.dropped_count += 1
            item = FrameItem(frame, frame_number, timestamp)
            self.buffer.append(item)
            return True

    def pop(self) -> Optional[FrameItem]:
        """
        Pop and return the oldest frame from the buffer.
        """
        with self.lock:
            if len(self.buffer) == 0:
                return None
            return self.buffer.popleft()

    def get_latest(self) -> Optional[FrameItem]:
        """
        Peek latest frame without removing it.
        """
        with self.lock:
            if len(self.buffer) == 0:
                return None
            return self.buffer[-1]

    def clear(self) -> None:
        """
        Flush all buffered frames.
        """
        with self.lock:
            self.buffer.clear()

    def size(self) -> int:
        with self.lock:
            return len(self.buffer)

    def is_full(self) -> bool:
        with self.lock:
            return len(self.buffer) >= self.max_size

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "size": len(self.buffer),
                "max_size": self.max_size,
                "dropped_count": self.dropped_count,
            }

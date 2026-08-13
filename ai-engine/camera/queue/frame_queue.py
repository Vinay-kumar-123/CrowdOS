import asyncio
import time
from typing import Optional, Dict, Any
from camera.buffer.frame_buffer import FrameItem
from camera.utils.logger import camera_logger


class FrameQueue:
    """
    Asynchronous asyncio.Queue wrapper with Backpressure strategies (DROP_OLDEST / DROP_NEWEST)
    and comprehensive runtime queue monitoring statistics.
    """
    def __init__(self, max_size: int = 60, backpressure_policy: str = "DROP_OLDEST"):
        self.max_size = max_size
        self.backpressure_policy = backpressure_policy.upper()
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        
        self.total_produced = 0
        self.total_consumed = 0
        self.total_dropped = 0
        self.queue_overflow_count = 0
        self.peak_queue_size = 0
        
        self.total_wait_time_seconds = 0.0
        self.wait_time_samples = 0

    async def put(self, item: FrameItem) -> bool:
        """
        Put a FrameItem into the queue. Applies backpressure frame dropping if queue is full.
        """
        current_sz = self.queue.qsize()

        if self.queue.full():
            self.total_dropped += 1
            self.queue_overflow_count += 1
            self.peak_queue_size = self.max_size
            camera_logger.warning(
                f"Queue Overflow detected (Capacity: {self.max_size}). Policy: {self.backpressure_policy}",
                extra={"event_type": "QUEUE_OVERFLOW"}
            )
            if self.backpressure_policy == "DROP_OLDEST":
                try:
                    dropped = self.queue.get_nowait()
                    self.queue.task_done()
                    del dropped
                except asyncio.QueueEmpty:
                    pass
                await self.queue.put(item)
                self.total_produced += 1
                return True
            else:  # DROP_NEWEST
                camera_logger.debug("FrameQueue full: Dropping incoming frame (DROP_NEWEST)")
                return False

        await self.queue.put(item)
        self.total_produced += 1
        self.peak_queue_size = max(self.peak_queue_size, self.queue.qsize())
        return True

    async def get(self, timeout: Optional[float] = 1.0) -> Optional[FrameItem]:
        """
        Consume a FrameItem from the queue with an optional timeout and track queue wait time.
        """
        get_start = time.time()
        try:
            if timeout:
                item = await asyncio.wait_for(self.queue.get(), timeout=timeout)
            else:
                item = await self.queue.get()
            
            wait_time = time.time() - get_start
            self.total_wait_time_seconds += wait_time
            self.wait_time_samples += 1
            self.total_consumed += 1
            self.queue.task_done()
            return item
        except asyncio.TimeoutError:
            return None

    def empty(self) -> bool:
        return self.queue.empty()

    def full(self) -> bool:
        return self.queue.full()

    def size(self) -> int:
        return self.queue.qsize()

    def get_statistics(self) -> Dict[str, Any]:
        curr_size = self.queue.qsize()
        usage_pct = round((curr_size / self.max_size) * 100.0, 2) if self.max_size > 0 else 0.0
        avg_wait = round((self.total_wait_time_seconds / self.wait_time_samples) * 1000.0, 2) if self.wait_time_samples > 0 else 0.0

        return {
            "current_queue_size": curr_size,
            "max_queue_size": self.max_size,
            "queue_usage_pct": usage_pct,
            "total_produced": self.total_produced,
            "total_consumed": self.total_consumed,
            "total_dropped": self.total_dropped,
            "overflow_count": self.queue_overflow_count,
            "peak_queue_size": self.peak_queue_size,
            "avg_queue_wait_time_ms": avg_wait,
            "backpressure_policy": self.backpressure_policy,
        }

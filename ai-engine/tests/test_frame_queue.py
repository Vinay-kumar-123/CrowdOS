import pytest
import numpy as np
from camera.buffer.frame_buffer import FrameItem
from camera.queue.frame_queue import FrameQueue


@pytest.mark.asyncio
async def test_frame_queue_backpressure_drop_oldest():
    queue = FrameQueue(max_size=2, backpressure_policy="DROP_OLDEST")
    frame = np.zeros((10, 10, 3), dtype=np.uint8)

    await queue.put(FrameItem(frame, 1))
    await queue.put(FrameItem(frame, 2))
    assert queue.full() is True

    # Pushing 3rd frame drops frame #1 (oldest)
    await queue.put(FrameItem(frame, 3))
    assert queue.size() == 2

    item = await queue.get()
    assert item.frame_number == 2  # Frame 1 was dropped

    stats = queue.get_statistics()
    assert stats["total_dropped"] == 1
    assert stats["overflow_count"] == 1
    assert stats["peak_queue_size"] == 2
    assert stats["queue_usage_pct"] == 50.0  # 1 item left in queue of max 2

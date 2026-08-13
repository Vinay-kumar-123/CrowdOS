import pytest
import numpy as np
from camera.buffer.frame_buffer import FrameBuffer


def test_frame_buffer_fifo():
    buffer = FrameBuffer(max_size=3)
    dummy_frame1 = np.ones((100, 100, 3), dtype=np.uint8) * 1
    dummy_frame2 = np.ones((100, 100, 3), dtype=np.uint8) * 2
    dummy_frame3 = np.ones((100, 100, 3), dtype=np.uint8) * 3

    buffer.push(dummy_frame1, 1)
    buffer.push(dummy_frame2, 2)
    buffer.push(dummy_frame3, 3)

    assert buffer.size() == 3
    assert buffer.is_full() is True

    item1 = buffer.pop()
    assert item1 is not None
    assert item1.frame_number == 1

    # Overwrite test
    dummy_frame4 = np.ones((100, 100, 3), dtype=np.uint8) * 4
    dummy_frame5 = np.ones((100, 100, 3), dtype=np.uint8) * 5
    buffer.push(dummy_frame4, 4)
    buffer.push(dummy_frame5, 5)  # Triggers drop of oldest

    stats = buffer.get_stats()
    assert stats["dropped_count"] >= 1

import asyncio
import time
from typing import Optional
from camera.capture.base import BaseCameraCapture
from camera.buffer.frame_buffer import FrameBuffer
from camera.queue.frame_queue import FrameQueue
from camera.health.health_service import CameraHealthService
from camera.utils.logger import camera_logger


class FrameProducer:
    """
    Asynchronous Frame Producer running continuous frame acquisition loop.
    Uses asyncio.to_thread for non-blocking OpenCV frame decoding.
    """
    def __init__(
        self,
        capture: BaseCameraCapture,
        buffer: FrameBuffer,
        queue: FrameQueue,
        health: CameraHealthService,
        fps_limit: float = 30.0,
    ):
        self.capture = capture
        self.buffer = buffer
        self.queue = queue
        self.health = health
        self.fps_limit = fps_limit
        self.is_running = False
        self.frame_counter = 0

    async def run(self) -> None:
        self.is_running = True
        camera_id = self.capture.metadata.camera_id
        target_frame_time = 1.0 / self.fps_limit if self.fps_limit > 0 else 0.0

        camera_logger.info(
            f"FrameProducer started for camera {camera_id} @ max {self.fps_limit} FPS",
            extra={"camera_id": camera_id, "event_type": "PRODUCER_STARTED"}
        )

        while self.is_running:
            if not self.capture.is_connected():
                await asyncio.sleep(0.1)
                continue

            loop_start = time.time()

            # Non-blocking async frame read offloaded to worker thread pool
            try:
                success, frame = await asyncio.to_thread(self.capture.read_frame)
            except Exception as e:
                camera_logger.error(
                    f"Frame read exception for camera {camera_id}: {e}",
                    extra={"camera_id": camera_id, "event_type": "CAMERA_ERROR"}
                )
                self.health.record_dropped_frame()
                await asyncio.sleep(0.01)
                continue

            if not success or frame is None:
                self.health.record_dropped_frame()
                await asyncio.sleep(0.01)
                continue

            self.frame_counter += 1
            now = time.time()

            # Push to Ring Buffer (thread-safe sync)
            self.buffer.push(frame, self.frame_counter, now)

            # Push to Async Queue (backpressure managed)
            item = self.buffer.get_latest()
            if item:
                pushed = await self.queue.put(item)
                if not pushed:
                    self.health.record_dropped_frame()

            # Record health metrics
            self.health.record_frame(now)

            # Throttle loop to target FPS limit
            elapsed = time.time() - loop_start
            sleep_time = max(0.0, target_frame_time - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        camera_logger.info(
            f"FrameProducer stopped for camera {camera_id}",
            extra={"camera_id": camera_id, "event_type": "PRODUCER_STOPPED"}
        )

    def stop(self) -> None:
        self.is_running = False

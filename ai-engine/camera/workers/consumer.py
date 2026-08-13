import asyncio
from typing import Callable, Optional
from camera.queue.frame_queue import FrameQueue
from camera.utils.logger import camera_logger


class FrameConsumer:
    """
    Asynchronous Frame Consumer worker pulling frames from FrameQueue.
    """
    def __init__(
        self,
        camera_id: str,
        queue: FrameQueue,
        frame_callback: Optional[Callable] = None,
    ):
        self.camera_id = camera_id
        self.queue = queue
        self.frame_callback = frame_callback
        self.is_running = False

    async def run(self) -> None:
        self.is_running = True
        camera_logger.info(
            f"FrameConsumer started for camera {self.camera_id}",
            extra={"camera_id": self.camera_id, "event_type": "CONSUMER_STARTED"}
        )

        while self.is_running:
            item = await self.queue.get(timeout=0.5)
            if item is None:
                await asyncio.sleep(0.01)
                continue

            if self.frame_callback:
                try:
                    if asyncio.iscoroutinefunction(self.frame_callback):
                        await self.frame_callback(self.camera_id, item)
                    else:
                        self.frame_callback(self.camera_id, item)
                except Exception as e:
                    camera_logger.error(
                        f"Frame callback execution error: {e}",
                        extra={"camera_id": self.camera_id}
                    )

        camera_logger.info(
            f"FrameConsumer stopped for camera {self.camera_id}",
            extra={"camera_id": self.camera_id, "event_type": "CONSUMER_STOPPED"}
        )

    def stop(self) -> None:
        self.is_running = False

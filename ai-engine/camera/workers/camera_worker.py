import asyncio
from typing import Optional, Callable
from camera.capture.base import BaseCameraCapture
from camera.buffer.frame_buffer import FrameBuffer
from camera.queue.frame_queue import FrameQueue
from camera.health.health_service import CameraHealthService
from camera.workers.producer import FrameProducer
from camera.workers.consumer import FrameConsumer
from camera.workers.health_worker import HealthWorker
from camera.utils.logger import camera_logger


class CameraWorker:
    """
    Per-Camera Async Task Manager encapsulating Producer, Consumer, and Health Worker tasks.
    """
    def __init__(
        self,
        capture: BaseCameraCapture,
        buffer: FrameBuffer,
        queue: FrameQueue,
        health: CameraHealthService,
        frame_callback: Optional[Callable] = None,
        reconnect_callback: Optional[Callable] = None,
        fps_limit: float = 30.0,
    ):
        self.camera_id = capture.metadata.camera_id
        self.capture = capture
        self.buffer = buffer
        self.queue = queue
        self.health = health
        
        self.producer = FrameProducer(capture, buffer, queue, health, fps_limit)
        self.consumer = FrameConsumer(self.camera_id, queue, frame_callback)
        self.health_worker = HealthWorker(self.camera_id, health, check_interval=2.0, reconnect_callback=reconnect_callback)

        self.producer_task: Optional[asyncio.Task] = None
        self.consumer_task: Optional[asyncio.Task] = None
        self.health_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        camera_logger.info(
            f"Starting CameraWorker tasks for camera {self.camera_id}...",
            extra={"camera_id": self.camera_id, "event_type": "CAMERA_WORKER_STARTING"}
        )
        self.producer_task = asyncio.create_task(self.producer.run())
        self.consumer_task = asyncio.create_task(self.consumer.run())
        self.health_task = asyncio.create_task(self.health_worker.run())

    async def stop(self) -> None:
        camera_logger.info(
            f"Stopping CameraWorker tasks for camera {self.camera_id}...",
            extra={"camera_id": self.camera_id, "event_type": "CAMERA_WORKER_STOPPING"}
        )
        self.producer.stop()
        self.consumer.stop()
        self.health_worker.stop()

        tasks = [t for t in [self.producer_task, self.consumer_task, self.health_task] if t and not t.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

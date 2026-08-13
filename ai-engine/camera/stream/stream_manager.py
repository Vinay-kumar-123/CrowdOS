import asyncio
from typing import Optional, Dict, Any, Callable
from camera.capture.base import BaseCameraCapture
from camera.buffer.frame_buffer import FrameBuffer, FrameItem
from camera.queue.frame_queue import FrameQueue
from camera.health.health_service import CameraHealthService
from camera.workers.camera_worker import CameraWorker
from camera.utils.logger import camera_logger


class StreamManager:
    """
    Manages stream control states (Start, Stop, Pause, Resume) and frame pipeline operations for a single camera stream.
    Exposes comprehensive runtime statistics.
    """
    def __init__(
        self,
        capture: BaseCameraCapture,
        buffer_size: int = 30,
        queue_size: int = 60,
        fps_limit: float = 30.0,
        frame_callback: Optional[Callable] = None,
        reconnect_callback: Optional[Callable] = None,
    ):
        self.capture = capture
        self.camera_id = capture.metadata.camera_id
        self.fps_limit = fps_limit
        
        self.buffer = FrameBuffer(max_size=buffer_size)
        self.queue = FrameQueue(max_size=queue_size)
        self.health = CameraHealthService(self.camera_id)
        
        self.worker = CameraWorker(
            capture=capture,
            buffer=self.buffer,
            queue=self.queue,
            health=self.health,
            frame_callback=frame_callback,
            reconnect_callback=reconnect_callback,
            fps_limit=fps_limit,
        )

        self.is_paused = False

    async def start_stream(self) -> bool:
        camera_logger.info(
            f"Starting stream for camera {self.camera_id}...",
            extra={"camera_id": self.camera_id, "event_type": "STREAM_STARTING"}
        )
        success = self.capture.connect()
        if not success:
            self.health.mark_disconnected()
            return False

        self.health.mark_connected()
        await self.worker.start()
        return True

    async def stop_stream(self) -> None:
        camera_logger.info(
            f"Stopping stream for camera {self.camera_id}...",
            extra={"camera_id": self.camera_id, "event_type": "STREAM_STOPPING"}
        )
        await self.worker.stop()
        self.capture.disconnect()
        self.health.mark_disconnected()

    def pause_stream(self) -> None:
        self.is_paused = True
        self.worker.producer.is_running = False
        camera_logger.info(
            f"Stream paused for camera {self.camera_id}",
            extra={"camera_id": self.camera_id, "event_type": "STREAM_PAUSED"}
        )

    def resume_stream(self) -> None:
        self.is_paused = False
        self.worker.producer.is_running = True
        camera_logger.info(
            f"Stream resumed for camera {self.camera_id}",
            extra={"camera_id": self.camera_id, "event_type": "STREAM_RESUMED"}
        )

    def read_latest_frame(self) -> Optional[FrameItem]:
        return self.buffer.get_latest()

    def get_runtime_statistics(self) -> Dict[str, Any]:
        """
        Returns complete runtime statistics for this camera stream.
        """
        health_report = self.health.get_health_report()
        queue_stats = self.queue.get_statistics()
        meta = self.capture.metadata.to_dict()

        # Compute average FPS over uptime
        uptime = health_report["uptime_seconds"]
        received = health_report["total_frames_received"]
        avg_fps = round(received / uptime, 2) if uptime > 0 else 0.0

        return {
            "camera_id": meta["camera_id"],
            "camera_name": meta["camera_name"],
            "camera_type": meta["camera_type"],
            "camera_source": meta["camera_source"],
            "resolution": meta["resolution"],
            "configured_fps": meta["fps"],
            "current_fps": health_report["rolling_fps"],
            "average_fps": avg_fps,
            "current_status": health_report["status"],
            "frames_received": health_report["total_frames_received"],
            "frames_dropped": health_report["total_frames_dropped"],
            "reconnect_count": health_report["reconnect_count"],
            "uptime_seconds": uptime,
            "latency_ms": health_report["current_latency_ms"],
            "avg_latency_ms": health_report["avg_latency_ms"],
            "last_frame_timestamp": health_report["last_frame_time"],
            "health_score": health_report["health_percentage"],
            "health_summary": {
                "healthy": health_report["healthy"],
                "reconnect_history": health_report["reconnect_history"],
            },
            "queue_statistics": queue_stats,
            "buffer_statistics": self.buffer.get_stats(),
        }

    def get_stream_health(self) -> Dict[str, Any]:
        return self.get_runtime_statistics()

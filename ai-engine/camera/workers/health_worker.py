import asyncio
from camera.health.health_service import CameraHealthService
from camera.utils.logger import camera_logger


class HealthWorker:
    """
    Asynchronous Health Worker running periodic heartbeat audit & auto-reconnect checks.
    """
    def __init__(
        self,
        camera_id: str,
        health_service: CameraHealthService,
        check_interval: float = 2.0,
        reconnect_callback=None,
    ):
        self.camera_id = camera_id
        self.health_service = health_service
        self.check_interval = check_interval
        self.reconnect_callback = reconnect_callback
        self.is_running = False

    async def run(self) -> None:
        self.is_running = True
        camera_logger.info(
            f"HealthWorker monitoring started for camera {self.camera_id}",
            extra={"camera_id": self.camera_id, "event_type": "HEALTH_WORKER_STARTED"}
        )

        while self.is_running:
            await asyncio.sleep(self.check_interval)
            report = self.health_service.get_health_report()

            # Trigger auto-reconnect if camera is marked disconnected or unhealthy
            if not report["healthy"] and not report["reconnecting"]:
                camera_logger.warning(
                    f"Camera {self.camera_id} detected unhealthy/disconnected. Triggering auto-reconnect.",
                    extra={"camera_id": self.camera_id, "event_type": "CAMERA_UNHEALTHY"}
                )
                if self.reconnect_callback:
                    if asyncio.iscoroutinefunction(self.reconnect_callback):
                        await self.reconnect_callback(self.camera_id)
                    else:
                        self.reconnect_callback(self.camera_id)

    def stop(self) -> None:
        self.is_running = False

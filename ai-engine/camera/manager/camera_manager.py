import asyncio
from typing import Dict, List, Optional, Any, Callable
from camera.capture.base import CameraMetadata
from camera.capture.factory import CameraFactory
from camera.stream.stream_manager import StreamManager
from camera.config.settings import camera_settings
from camera.utils.logger import camera_logger


class CameraManager:
    """
    Central Orchestrator for managing multi-camera stream lifecycles independently
    and providing system-wide camera runtime statistics.
    """
    def __init__(self):
        self.streams: Dict[str, StreamManager] = {}

    def register_camera(
        self,
        camera_id: str,
        camera_name: str,
        camera_type: str,
        camera_source: str,
        fps: float = 30.0,
        resolution: tuple = (1920, 1080),
        frame_callback: Optional[Callable] = None,
    ) -> bool:
        if camera_id in self.streams:
            camera_logger.warning(
                f"Camera {camera_id} is already registered.",
                extra={"camera_id": camera_id}
            )
            return False

        if len(self.streams) >= camera_settings.MAX_CAMERAS:
            camera_logger.error("Maximum registered camera capacity reached.")
            return False

        metadata = CameraMetadata(
            camera_id=camera_id,
            camera_name=camera_name,
            camera_type=camera_type,
            camera_source=camera_source,
            fps=fps,
            resolution=resolution,
        )

        capture = CameraFactory.create_camera(metadata)
        
        stream_mgr = StreamManager(
            capture=capture,
            buffer_size=camera_settings.FRAME_BUFFER_SIZE,
            queue_size=camera_settings.MAX_QUEUE_SIZE,
            fps_limit=fps,
            frame_callback=frame_callback,
            reconnect_callback=self.reconnect_camera,
        )

        self.streams[camera_id] = stream_mgr
        camera_logger.info(
            f"Successfully registered camera: '{camera_name}' ({camera_type} -> {camera_source})",
            extra={"camera_id": camera_id, "event_type": "CAMERA_REGISTERED"}
        )
        return True

    async def start_camera(self, camera_id: str) -> bool:
        stream = self.streams.get(camera_id)
        if not stream:
            camera_logger.error(f"Cannot start: Camera {camera_id} not found.")
            return False

        return await stream.start_stream()

    async def stop_camera(self, camera_id: str) -> bool:
        stream = self.streams.get(camera_id)
        if not stream:
            camera_logger.error(f"Cannot stop: Camera {camera_id} not found.")
            return False

        await stream.stop_stream()
        return True

    async def restart_camera(self, camera_id: str) -> bool:
        camera_logger.info(f"Restarting camera {camera_id}...", extra={"camera_id": camera_id})
        await self.stop_camera(camera_id)
        await asyncio.sleep(1.0)
        return await self.start_camera(camera_id)

    async def reconnect_camera(self, camera_id: str) -> bool:
        stream = self.streams.get(camera_id)
        if not stream:
            return False

        camera_logger.warning(
            f"Attempting camera reconnection for {camera_id}...",
            extra={"camera_id": camera_id, "event_type": "CAMERA_RECONNECTING"}
        )
        stream.health.mark_reconnecting()

        for attempt in range(1, camera_settings.RECONNECT_ATTEMPTS + 1):
            camera_logger.info(
                f"Reconnection attempt {attempt}/{camera_settings.RECONNECT_ATTEMPTS} for {camera_id}...",
                extra={"camera_id": camera_id}
            )
            success = await self.restart_camera(camera_id)
            if success:
                camera_logger.info(
                    f"Reconnection successful for camera {camera_id}!",
                    extra={"camera_id": camera_id, "event_type": "CAMERA_CONNECTED"}
                )
                return True
            await asyncio.sleep(camera_settings.RECONNECT_DELAY_SECONDS)

        camera_logger.error(
            f"Failed to reconnect camera {camera_id} after {camera_settings.RECONNECT_ATTEMPTS} attempts.",
            extra={"camera_id": camera_id, "event_type": "CAMERA_ERROR"}
        )
        return False

    async def remove_camera(self, camera_id: str) -> bool:
        if camera_id not in self.streams:
            return False

        await self.stop_camera(camera_id)
        del self.streams[camera_id]
        camera_logger.info(
            f"Removed camera {camera_id} from CameraManager.",
            extra={"camera_id": camera_id, "event_type": "CAMERA_REMOVED"}
        )
        return True

    def get_camera_status(self, camera_id: str) -> Optional[str]:
        stream = self.streams.get(camera_id)
        return stream.health.status if stream else None

    def get_camera_statistics(self, camera_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves detailed runtime statistics for a specific camera.
        """
        stream = self.streams.get(camera_id)
        return stream.get_runtime_statistics() if stream else None

    def get_camera_health(self, camera_id: str) -> Optional[Dict[str, Any]]:
        return self.get_camera_statistics(camera_id)

    def list_active_cameras(self) -> List[Dict[str, Any]]:
        return [
            stream.get_runtime_statistics()
            for stream in self.streams.values()
        ]

    async def stop_all(self) -> None:
        camera_logger.info("Stopping all registered camera streams...")
        for camera_id in list(self.streams.keys()):
            await self.stop_camera(camera_id)

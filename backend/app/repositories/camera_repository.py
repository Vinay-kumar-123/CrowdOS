"""
Camera Repository — Sprint 16.

Manages persistent camera documents in the MongoDB 'cameras' collection.
Supports venue isolation, safe health telemetry updates, startup reconciliation,
and graceful degradation when MongoDB is unavailable.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pymongo.errors import DuplicateKeyError
from app.models.camera import CameraDBModel, CameraStatus
from app.repositories.base import BaseRepository
from app.core.camera_security import sanitize_error_message

logger = logging.getLogger("crowdos.repositories.camera")


class CameraRepository(BaseRepository[CameraDBModel]):
    """
    Repository for persisting and querying camera configurations and health.
    """

    def __init__(self, collection):
        super().__init__(collection, CameraDBModel)

    async def get_by_camera_id(self, camera_id: str) -> Optional[CameraDBModel]:
        """Fetch camera document by unique camera_id."""
        return await self.find_one({"camera_id": camera_id})

    async def list_by_venue(self, venue_id: str, is_active: Optional[bool] = None) -> List[CameraDBModel]:
        """List cameras belonging strictly to a venue."""
        query: Dict[str, Any] = {"venue_id": venue_id}
        if is_active is not None:
            query["is_active"] = is_active
        return await self.find_many(query, sort=[("created_at", -1)])

    async def save_camera(self, camera: CameraDBModel) -> Optional[CameraDBModel]:
        """
        Persist new camera configuration with duplicate key protection.
        """
        if not self.is_available:
            return camera

        existing = await self.get_by_camera_id(camera.camera_id)
        if existing:
            logger.info(f"Duplicate camera_id '{camera.camera_id}' detected. Updating existing.")
            doc = camera.to_mongo()
            await self.collection.replace_one({"camera_id": camera.camera_id}, doc, upsert=True)
            return camera

        try:
            doc = camera.to_mongo()
            await self.collection.insert_one(doc)
            return camera
        except DuplicateKeyError:
            logger.info(f"Duplicate camera_id '{camera.camera_id}' caught by unique index.")
            return camera
        except Exception as e:
            logger.error(f"Failed to persist camera '{camera.camera_id}': {e}")
            return camera

    async def update_health(
        self,
        camera_id: str,
        status: CameraStatus,
        measured_fps: float = 0.0,
        processing_latency_ms: float = 0.0,
        reconnect_count: int = 0,
        last_frame_at: Optional[datetime] = None,
        last_successful_processing_at: Optional[datetime] = None,
        last_error_at: Optional[datetime] = None,
        last_error_message: Optional[str] = None,
    ) -> bool:
        """
        Update runtime health fields for a camera.
        """
        if not self.is_available:
            return False

        now_utc = datetime.now(timezone.utc)
        update_data: Dict[str, Any] = {
            "status": status.value if hasattr(status, "value") else str(status),
            "measured_fps": round(measured_fps, 2),
            "processing_latency_ms": round(processing_latency_ms, 2),
            "reconnect_count": reconnect_count,
            "health_updated_at": now_utc,
        }
        if last_frame_at is not None:
            update_data["last_frame_at"] = last_frame_at
        if last_successful_processing_at is not None:
            update_data["last_successful_processing_at"] = last_successful_processing_at
        if last_error_at is not None:
            update_data["last_error_at"] = last_error_at
        if last_error_message is not None:
            update_data["last_error_message"] = sanitize_error_message(last_error_message)

        try:
            res = await self.collection.update_one(
                {"camera_id": camera_id},
                {"$set": update_data}
            )
            return res.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update camera health for '{camera_id}': {e}")
            return False

    async def update_status(self, camera_id: str, status: CameraStatus) -> bool:
        """Update only status and health_updated_at."""
        if not self.is_available:
            return False
        try:
            status_val = status.value if hasattr(status, "value") else str(status)
            res = await self.collection.update_one(
                {"camera_id": camera_id},
                {"$set": {"status": status_val, "health_updated_at": datetime.now(timezone.utc)}}
            )
            return res.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update status for '{camera_id}': {e}")
            return False

    async def delete_camera(self, camera_id: str) -> bool:
        """Delete camera record by camera_id."""
        if not self.is_available:
            return False
        try:
            res = await self.collection.delete_one({"camera_id": camera_id})
            return res.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete camera '{camera_id}': {e}")
            return False

    async def reconcile_startup_statuses(self) -> int:
        """
        On application restart, reconcile any cameras previously marked ONLINE or RECONNECTING to OFFLINE.
        Guarantees that persistent storage never falsely claims a camera is ONLINE when the runtime is stopped.
        """
        if not self.is_available:
            return 0
        try:
            now_utc = datetime.now(timezone.utc)
            res = await self.collection.update_many(
                {"status": {"$in": ["ONLINE", "RECONNECTING"]}},
                {"$set": {"status": "OFFLINE", "health_updated_at": now_utc}}
            )
            reconciled = res.modified_count
            if reconciled > 0:
                logger.info(f"Reconciled {reconciled} camera statuses from ONLINE/RECONNECTING to OFFLINE on startup.")
            return reconciled
        except Exception as e:
            logger.warning(f"Startup camera status reconciliation notice: {e}")
            return 0

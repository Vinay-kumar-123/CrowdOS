"""
Alert Repository — Sprint 10.
"""
from typing import Optional, List
from app.models.alert import AlertDBModel
from app.repositories.base import BaseRepository


class AlertRepository(BaseRepository[AlertDBModel]):
    """
    Repository for persisting and querying operational alerts and anomaly signals in MongoDB.
    """

    def __init__(self, collection):
        super().__init__(collection, AlertDBModel)

    async def get_by_alert_id(self, alert_id: str) -> Optional[AlertDBModel]:
        """Fetch alert document by alert_id."""
        return await self.find_one({"alert_id": alert_id})

    async def save_or_update_alert(self, alert: AlertDBModel) -> Optional[AlertDBModel]:
        """Insert or update alert document in MongoDB."""
        if not self.is_available:
            return alert

        payload = alert.to_mongo()
        await self.update_by_filter(
            {"alert_id": alert.alert_id},
            payload,
            upsert=True,
        )
        return alert

    async def list_active_alerts(self, venue_id: str) -> List[AlertDBModel]:
        """Fetch active alerts for a venue."""
        return await self.find_many(
            {"venue_id": venue_id, "status": "ACTIVE"},
            sort=[("created_at", -1)],
        )

    async def list_all_alerts(self, venue_id: str, limit: int = 100) -> List[AlertDBModel]:
        """Fetch all alerts (active and resolved) for a venue."""
        return await self.find_many(
            {"venue_id": venue_id},
            sort=[("created_at", -1)],
            limit=limit,
        )

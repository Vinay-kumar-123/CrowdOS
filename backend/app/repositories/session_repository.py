"""
Session Repository — Sprint 10.
"""
from typing import Optional, List, Dict, Any
from app.models.session import SessionDBModel
from app.repositories.base import BaseRepository


class SessionRepository(BaseRepository[SessionDBModel]):
    """
    Repository for managing continuous monitoring session records in MongoDB.
    """

    def __init__(self, collection):
        super().__init__(collection, SessionDBModel)

    async def get_by_session_id(self, session_id: str) -> Optional[SessionDBModel]:
        """Fetch session document by session_id."""
        return await self.find_one({"session_id": session_id})

    async def list_by_venue(self, venue_id: str, limit: int = 100) -> List[SessionDBModel]:
        """List sessions for a venue ordered by creation time descending."""
        return await self.find_many(
            {"venue_id": venue_id},
            sort=[("created_at", -1)],
            limit=limit,
        )

    async def get_active_session(self, venue_id: str) -> Optional[SessionDBModel]:
        """Find the currently active session for a venue."""
        return await self.find_one({"venue_id": venue_id, "status": "ACTIVE"})

    async def update_session_state(
        self,
        session_id: str,
        status: str,
        additional_fields: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update the session status and timestamps in MongoDB."""
        update_data = {"status": status}
        if additional_fields:
            update_data.update(additional_fields)

        return await self.update_by_filter(
            {"session_id": session_id},
            update_data,
            upsert=False,
        )

    async def save_session_summary(
        self,
        session_id: str,
        summary: Dict[str, Any],
        stopped_at: Optional[str] = None,
    ) -> bool:
        """Persist the final immutable SessionSummary generated when session is stopped."""
        update_data = {
            "status": "STOPPED",
            "summary": summary,
        }
        if stopped_at:
            update_data["stopped_at"] = stopped_at

        return await self.update_by_filter(
            {"session_id": session_id},
            update_data,
            upsert=False,
        )

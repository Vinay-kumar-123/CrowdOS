"""
Event Repository — Sprint 10.

Manages persistent operational movement event records (ENTRY / EXIT) with duplicate event protection.
Privacy guarantee: Zero biometric metadata persisted.
"""
import logging
from typing import Optional, List
from pymongo.errors import DuplicateKeyError
from app.models.event import EventDBModel
from app.repositories.base import BaseRepository

logger = logging.getLogger("crowdos.repositories.event")


class EventRepository(BaseRepository[EventDBModel]):
    """
    Repository for persisting and querying movement events in MongoDB.
    """

    def __init__(self, collection):
        super().__init__(collection, EventDBModel)

    async def get_by_event_id(self, event_id: str) -> Optional[EventDBModel]:
        """Fetch event document by event_id."""
        return await self.find_one({"event_id": event_id})

    async def save_event(self, event: EventDBModel) -> Optional[EventDBModel]:
        """
        Persist movement event with duplicate key safety.
        Protects against duplicate event insertions both via application-level check
        and MongoDB unique index DuplicateKeyError handling.
        """
        if not self.is_available:
            return event

        # Application-level check
        existing = await self.get_by_event_id(event.event_id)
        if existing:
            logger.info(f"Duplicate event_id detected in MongoDB: '{event.event_id}'. Event ignored.")
            return existing

        try:
            doc = event.to_mongo()
            await self.collection.insert_one(doc)
            return event
        except DuplicateKeyError:
            logger.info(f"Duplicate event_id detected (unique index): '{event.event_id}'. Event ignored.")
            return event
        except Exception as e:
            logger.error(f"Failed to persist event '{event.event_id}': {e}")
            return event

    async def list_events_by_session(
        self,
        session_id: str,
        limit: int = 100,
        event_type: Optional[str] = None,
    ) -> List[EventDBModel]:
        """List historical events for a specific monitoring session."""
        query = {"session_id": session_id}
        if event_type:
            query["event_type"] = event_type.upper()

        return await self.find_many(query, sort=[("timestamp", -1)], limit=limit)

    async def list_events_by_venue(
        self,
        venue_id: str,
        limit: int = 100,
    ) -> List[EventDBModel]:
        """List historical events for a venue."""
        return await self.find_many({"venue_id": venue_id}, sort=[("timestamp", -1)], limit=limit)

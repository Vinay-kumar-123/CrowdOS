"""
Venue Repository — Sprint 10.
"""
from typing import Optional, List
from app.models.venue import VenueDBModel
from app.repositories.base import BaseRepository


class VenueRepository(BaseRepository[VenueDBModel]):
    """
    Repository for managing Venue persistence in MongoDB.
    """

    def __init__(self, collection):
        super().__init__(collection, VenueDBModel)

    async def get_by_venue_id(self, venue_id: str) -> Optional[VenueDBModel]:
        """Fetch venue document by venue_id."""
        return await self.find_one({"venue_id": venue_id})

    async def list_venues(self, limit: int = 100) -> List[VenueDBModel]:
        """List all active venues."""
        return await self.find_many({"is_active": True}, sort=[("created_at", -1)], limit=limit)

    async def upsert_venue(self, venue: VenueDBModel) -> Optional[VenueDBModel]:
        """Insert or update venue by venue_id."""
        if not self.is_available:
            return venue

        payload = venue.to_mongo()
        await self.update_by_filter(
            {"venue_id": venue.venue_id},
            payload,
            upsert=True,
        )
        return venue

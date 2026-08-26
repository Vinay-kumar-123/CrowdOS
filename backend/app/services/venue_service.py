"""
Venue Service — Sprint 10.

Manages persistent venue metadata in MongoDB and ensures synchronization
with in-memory VenueEngineRegistry.
"""
import logging
from typing import List, Optional, Dict, Any
from app.services.ai_engine_adapter import VenueEngineRegistry
from app.repositories.venue_repository import VenueRepository
from app.models.venue import VenueDBModel

logger = logging.getLogger("crowdos.venue_service")


class VenueService:
    """
    Service coordinating venue persistence and in-memory engine registry synchronization.
    """

    def __init__(
        self,
        registry: VenueEngineRegistry,
        venue_repo: Optional[VenueRepository] = None,
    ):
        self._registry = registry
        self._venue_repo = venue_repo

    async def register_venue(
        self,
        venue_id: str,
        name: str = "",
        capacity: int = 1000,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VenueDBModel:
        """
        Register a new venue or update capacity/metadata in both MongoDB and in-memory registry.
        """
        self._registry.get_or_create(venue_id=venue_id, venue_capacity=capacity)
        self._registry.update_capacity(venue_id=venue_id, venue_capacity=capacity)

        venue_model = VenueDBModel(
            venue_id=venue_id,
            name=name or f"Venue {venue_id}",
            capacity=capacity,
            description=description,
            metadata=metadata or {},
        )

        if self._venue_repo and self._venue_repo.is_available:
            await self._venue_repo.upsert_venue(venue_model)

        return venue_model

    async def get_venue(self, venue_id: str) -> Optional[VenueDBModel]:
        """Fetch venue from MongoDB or reconstruct from in-memory engine registry."""
        if self._venue_repo and self._venue_repo.is_available:
            venue = await self._venue_repo.get_by_venue_id(venue_id)
            if venue:
                return venue

        engines = self._registry.get(venue_id)
        if engines is not None:
            return VenueDBModel(
                venue_id=venue_id,
                name=f"Venue {venue_id}",
                capacity=engines.venue_capacity,
            )
        return None

    async def list_venues(self, limit: int = 100) -> List[str]:
        """Return list of all registered venue IDs from MongoDB and in-memory registry."""
        venue_ids = set(self._registry.list_venue_ids())

        if self._venue_repo and self._venue_repo.is_available:
            persisted_venues = await self._venue_repo.list_venues(limit=limit)
            for v in persisted_venues:
                venue_ids.add(v.venue_id)

        return sorted(list(venue_ids))

    async def reset_venue(self, venue_id: str) -> bool:
        """Reset venue in-memory state and clean up test records."""
        reg_reset = self._registry.reset_venue(venue_id)
        if self._venue_repo and self._venue_repo.is_available:
            await self._venue_repo.delete_one({"venue_id": venue_id})
        return reg_reset

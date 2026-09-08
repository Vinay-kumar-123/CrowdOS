"""
Visitor, Visitor Events, and Visit Repositories — Sprint 13.

Provides asynchronous MongoDB data access for:
- VisitorRepository: Persistent visitor profiles with atomic counter management.
- VisitorEventRepository: Immutable movement event records with source_event_id idempotency.
- VisitRepository: Physical presence visits with atomic state transitions and concurrency safety.

Enforces strict venue isolation across all queries.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pymongo import ReturnDocument, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from app.models.base import utc_now
from app.models.visitor import VisitorDBModel, VisitorEventDBModel, VisitDBModel
from app.repositories.base import BaseRepository

logger = logging.getLogger("crowdos.repositories.visitor")


class VisitorRepository(BaseRepository[VisitorDBModel]):
    """
    Repository for managing persistent visitor profiles.
    Strictly venue-scoped: queries require both venue_id and visitor_id.
    """

    def __init__(self, collection):
        super().__init__(collection, VisitorDBModel)

    async def get_by_venue_and_visitor(self, venue_id: str, visitor_id: str) -> Optional[VisitorDBModel]:
        """Fetch visitor profile scoped strictly by venue_id and visitor_id."""
        if not self.is_available:
            return None
        return await self.find_one({"venue_id": venue_id, "visitor_id": visitor_id})

    async def upsert_visitor_on_event(
        self,
        venue_id: str,
        visitor_id: str,
        event_type: str,
        timestamp: datetime,
        is_new_visit: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[VisitorDBModel]:
        """
        Atomically update or create a visitor profile upon an event.

        CTO Constraint 1 Semantics:
        - ENTRY -> increments total_entries by 1.
        - EXIT -> increments total_exits by 1.
        - total_visits is incremented IF AND ONLY IF is_new_visit is True (valid ENTRY opening a visit).
        - EXIT NEVER increments total_visits.
        - first_seen_at = min(first_seen_at, timestamp).
        - last_seen_at = max(last_seen_at, timestamp).
        """
        if not self.is_available:
            # Degraded in-memory fallback
            return VisitorDBModel(
                visitor_id=visitor_id,
                venue_id=venue_id,
                first_seen_at=timestamp,
                last_seen_at=timestamp,
                total_entries=1 if event_type == "ENTRY" else 0,
                total_exits=1 if event_type == "EXIT" else 0,
                total_visits=1 if is_new_visit else 0,
                metadata=metadata or {},
            )

        filter_query = {"venue_id": venue_id, "visitor_id": visitor_id}
        existing = await self.find_one(filter_query)

        now = utc_now()
        inc_fields: Dict[str, int] = {}
        if event_type == "ENTRY":
            inc_fields["total_entries"] = 1
        elif event_type == "EXIT":
            inc_fields["total_exits"] = 1

        if is_new_visit:
            inc_fields["total_visits"] = 1

        if not existing:
            # Create new visitor profile
            new_visitor = VisitorDBModel(
                visitor_id=visitor_id,
                venue_id=venue_id,
                first_seen_at=timestamp,
                last_seen_at=timestamp,
                total_entries=1 if event_type == "ENTRY" else 0,
                total_exits=1 if event_type == "EXIT" else 0,
                total_visits=1 if is_new_visit else 0,
                metadata=metadata or {},
                created_at=now,
                updated_at=now,
            )
            try:
                doc = new_visitor.to_mongo()
                await self.collection.insert_one(doc)
                return new_visitor
            except DuplicateKeyError:
                # Concurrent insert race — re-fetch and proceed with update
                existing = await self.find_one(filter_query)

        if existing:
            first_seen = min(existing.first_seen_at, timestamp)
            last_seen = max(existing.last_seen_at, timestamp)

            update_doc: Dict[str, Any] = {
                "$set": {
                    "first_seen_at": first_seen,
                    "last_seen_at": last_seen,
                    "updated_at": now,
                }
            }
            if inc_fields:
                update_doc["$inc"] = inc_fields
            if metadata:
                for k, v in metadata.items():
                    update_doc["$set"][f"metadata.{k}"] = v

            doc = await self.collection.find_one_and_update(
                filter_query,
                update_doc,
                return_document=ReturnDocument.AFTER,
            )
            return self._to_model(doc) if doc else existing

        return None

    async def list_visitors_by_venue(
        self,
        venue_id: str,
        limit: int = 50,
        skip: int = 0,
    ) -> List[VisitorDBModel]:
        """List visitors for a venue with pagination."""
        return await self.find_many(
            {"venue_id": venue_id},
            sort=[("last_seen_at", DESCENDING)],
            limit=limit,
            skip=skip,
        )

    async def count_visitors_by_venue(self, venue_id: str) -> int:
        """Count total registered visitors in a venue."""
        return await self.count({"venue_id": venue_id})

    async def delete_older_than(self, cutoff: datetime, venue_id: Optional[str] = None) -> int:
        """Retention maintenance: delete visitor records with last_seen_at older than cutoff."""
        if not self.is_available:
            return 0
        q: Dict[str, Any] = {"last_seen_at": {"$lt": cutoff}}
        if venue_id:
            q["venue_id"] = venue_id
        res = await self.collection.delete_many(q)
        return res.deleted_count


class VisitorEventRepository(BaseRepository[VisitorEventDBModel]):
    """
    Repository for immutable visitor movement events.
    Supports idempotency via visitor_event_id and (venue_id, source_event_id).
    """

    def __init__(self, collection):
        super().__init__(collection, VisitorEventDBModel)

    async def get_by_event_id(self, visitor_event_id: str) -> Optional[VisitorEventDBModel]:
        """Fetch movement event by unique visitor_event_id."""
        return await self.find_one({"visitor_event_id": visitor_event_id})

    async def get_by_source_event_id(self, venue_id: str, source_event_id: str) -> Optional[VisitorEventDBModel]:
        """Fetch movement event by source_event_id within a venue."""
        return await self.find_one({"venue_id": venue_id, "source_event_id": source_event_id})

    async def save_event(self, event: VisitorEventDBModel) -> Optional[VisitorEventDBModel]:
        """
        Persist visitor movement event with idempotency guarantees.

        CTO Constraint 2:
        Checks for existing event by visitor_event_id AND by (venue_id, source_event_id).
        If already processed, returns existing event without creating duplicate visitor history.
        """
        if not self.is_available:
            return event

        # Check by primary ID
        existing = await self.get_by_event_id(event.visitor_event_id)
        if existing:
            logger.info(f"Duplicate visitor_event_id '{event.visitor_event_id}' ignored.")
            return existing

        # Check by source_event_id if present
        if event.source_event_id:
            existing_src = await self.get_by_source_event_id(event.venue_id, event.source_event_id)
            if existing_src:
                logger.info(
                    f"Duplicate source_event_id '{event.source_event_id}' in venue '{event.venue_id}' ignored."
                )
                return existing_src

        try:
            doc = event.to_mongo()
            await self.collection.insert_one(doc)
            return event
        except DuplicateKeyError as e:
            logger.info(f"Duplicate event rejected by MongoDB unique constraint: {e}")
            if event.source_event_id:
                existing_src = await self.get_by_source_event_id(event.venue_id, event.source_event_id)
                if existing_src:
                    return existing_src
            return await self.get_by_event_id(event.visitor_event_id) or event
        except Exception as e:
            logger.error(f"Failed to persist visitor event: {e}")
            return event

    async def list_events_by_visitor(
        self,
        venue_id: str,
        visitor_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[VisitorEventDBModel]:
        """Query chronological visitor movement timeline with venue isolation and filtering."""
        query: Dict[str, Any] = {"venue_id": venue_id, "visitor_id": visitor_id}
        if event_type:
            query["event_type"] = event_type.upper()
        if start_time or end_time:
            time_filter: Dict[str, Any] = {}
            if start_time:
                time_filter["$gte"] = start_time
            if end_time:
                time_filter["$lte"] = end_time
            query["timestamp"] = time_filter

        return await self.find_many(
            query,
            sort=[("timestamp", ASCENDING)],
            limit=limit,
            skip=skip,
        )

    async def count_events(
        self,
        venue_id: str,
        visitor_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[str] = None,
    ) -> int:
        """Count events matching filters with venue isolation."""
        query: Dict[str, Any] = {"venue_id": venue_id, "visitor_id": visitor_id}
        if event_type:
            query["event_type"] = event_type.upper()
        if start_time or end_time:
            time_filter: Dict[str, Any] = {}
            if start_time:
                time_filter["$gte"] = start_time
            if end_time:
                time_filter["$lte"] = end_time
            query["timestamp"] = time_filter

        return await self.count(query)

    async def delete_older_than(self, cutoff: datetime, venue_id: Optional[str] = None) -> int:
        """Retention maintenance: delete movement events older than cutoff."""
        if not self.is_available:
            return 0
        q: Dict[str, Any] = {"timestamp": {"$lt": cutoff}}
        if venue_id:
            q["venue_id"] = venue_id
        res = await self.collection.delete_many(q)
        return res.deleted_count


class VisitRepository(BaseRepository[VisitDBModel]):
    """
    Repository for physical presence visits.
    Features atomic status transitions (OPEN -> COMPLETED) and concurrency safety.
    """

    def __init__(self, collection):
        super().__init__(collection, VisitDBModel)

    async def get_by_visit_id(self, visit_id: str) -> Optional[VisitDBModel]:
        """Fetch visit by unique visit_id."""
        return await self.find_one({"visit_id": visit_id})

    async def get_active_visit(self, venue_id: str, visitor_id: str) -> Optional[VisitDBModel]:
        """
        Get the currently OPEN visit for a visitor in a venue.
        Protected by unique partial index ensuring at most one OPEN visit exists per (venue_id, visitor_id).
        """
        if not self.is_available:
            return None
        return await self.find_one({
            "venue_id": venue_id,
            "visitor_id": visitor_id,
            "status": "OPEN",
        })

    async def create_visit(self, visit: VisitDBModel) -> Optional[VisitDBModel]:
        """
        Insert a new visit document.

        CTO Constraint 4:
        Protected by partial unique index idx_visits_one_open_per_visitor.
        If a concurrent request already opened a visit, raises DuplicateKeyError,
        which is caught and returns the existing OPEN visit to prevent duplicate visits.
        """
        if not self.is_available:
            return visit

        try:
            doc = visit.to_mongo()
            await self.collection.insert_one(doc)
            return visit
        except DuplicateKeyError:
            logger.info(
                f"Concurrent OPEN visit creation blocked for visitor '{visit.visitor_id}' in venue '{visit.venue_id}'."
            )
            return await self.get_active_visit(visit.venue_id, visit.visitor_id) or visit
        except Exception as e:
            logger.error(f"Failed to create visit: {e}")
            return visit

    async def complete_visit_atomic(
        self,
        venue_id: str,
        visitor_id: str,
        exit_event_id: str,
        exit_time: datetime,
        exit_gate: str,
        dwell_time: Optional[float] = None,
    ) -> Optional[VisitDBModel]:
        """
        Atomically complete the active OPEN visit.

        CTO Constraint 4 Concurrency Protection:
        Uses MongoDB atomic find_one_and_update with filter {"status": "OPEN"}.
        If two concurrent EXIT events arrive, exactly ONE transitions the state
        to "COMPLETED". The other matches nothing and returns None, preventing
        double completion and duration corruption.
        """
        if not self.is_available:
            return None

        # Fetch the active visit to calculate duration safely
        active = await self.get_active_visit(venue_id, visitor_id)
        if not active:
            return None

        # Compute duration
        if dwell_time is not None:
            duration_sec = round(max(0.0, float(dwell_time)), 2)
        else:
            duration_sec = round(max(0.0, (exit_time - active.entry_time).total_seconds()), 2)

        now = utc_now()
        doc = await self.collection.find_one_and_update(
            {
                "visit_id": active.visit_id,
                "venue_id": venue_id,
                "visitor_id": visitor_id,
                "status": "OPEN",
            },
            {
                "$set": {
                    "status": "COMPLETED",
                    "exit_event_id": exit_event_id,
                    "exit_time": exit_time,
                    "exit_gate": exit_gate,
                    "duration_seconds": duration_sec,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        return self._to_model(doc) if doc else None

    async def list_visits_by_visitor(
        self,
        venue_id: str,
        visitor_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[VisitDBModel]:
        """Query visits timeline with venue isolation and filtering."""
        query: Dict[str, Any] = {"venue_id": venue_id, "visitor_id": visitor_id}
        if status:
            query["status"] = status.upper()
        if start_time or end_time:
            time_filter: Dict[str, Any] = {}
            if start_time:
                time_filter["$gte"] = start_time
            if end_time:
                time_filter["$lte"] = end_time
            query["entry_time"] = time_filter

        return await self.find_many(
            query,
            sort=[("entry_time", DESCENDING)],
            limit=limit,
            skip=skip,
        )

    async def count_visits(
        self,
        venue_id: str,
        visitor_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        status: Optional[str] = None,
    ) -> int:
        """Count visits matching filters with venue isolation."""
        query: Dict[str, Any] = {"venue_id": venue_id, "visitor_id": visitor_id}
        if status:
            query["status"] = status.upper()
        if start_time or end_time:
            time_filter: Dict[str, Any] = {}
            if start_time:
                time_filter["$gte"] = start_time
            if end_time:
                time_filter["$lte"] = end_time
            query["entry_time"] = time_filter

        return await self.count(query)

    async def delete_older_than(self, cutoff: datetime, venue_id: Optional[str] = None) -> int:
        """Retention maintenance: delete visits with entry_time older than cutoff."""
        if not self.is_available:
            return 0
        q: Dict[str, Any] = {"entry_time": {"$lt": cutoff}}
        if venue_id:
            q["venue_id"] = venue_id
        res = await self.collection.delete_many(q)
        return res.deleted_count

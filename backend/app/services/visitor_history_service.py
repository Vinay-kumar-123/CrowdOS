"""
Visitor History Service — Sprint 13.

Core service orchestrating:
- Visitor profile persistence and atomic counter management
- Immutable visitor movement event logging
- Visit presence pairing state machine (ENTRY opens, EXIT completes)
- Idempotency on source_event_id and visitor_event_id
- Concurrency safety with atomic state transitions
- Strict venue isolation on all queries
- Retention policy maintenance
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Union
from app.models.visitor import (
    VisitorDBModel,
    VisitorEventDBModel,
    VisitDBModel,
    ensure_utc_datetime,
)
from app.repositories.visitor_repository import (
    VisitorRepository,
    VisitorEventRepository,
    VisitRepository,
)
from app.schemas.visitors import (
    VisitorResponse,
    VisitorEventItem,
    VisitorEventsListResponse,
    VisitItem,
    VisitsListResponse,
    VisitorHistoryResponse,
    _format_iso,
)
from app.core.exceptions import NotFoundException

logger = logging.getLogger("crowdos.visitor_history_service")


def parse_query_timestamp(val: Optional[Union[str, datetime]], is_end_of_day: bool = False) -> Optional[datetime]:
    """
    Parse a query parameter timestamp into a timezone-aware UTC datetime.
    Supports full ISO 8601 strings and date-only strings (YYYY-MM-DD).
    """
    if not val:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)

    val_str = str(val).strip()
    if len(val_str) == 10 and val_str.count("-") == 2:
        # Date only: e.g. "2026-09-08"
        if is_end_of_day:
            return datetime.fromisoformat(f"{val_str}T23:59:59.999999+00:00")
        return datetime.fromisoformat(f"{val_str}T00:00:00+00:00")

    return ensure_utc_datetime(val_str)


class VisitorHistoryService:
    """
    Service coordinating visitor profile management, movement history, and visit lifecycle.
    """

    def __init__(
        self,
        visitor_repo: Optional[VisitorRepository] = None,
        event_repo: Optional[VisitorEventRepository] = None,
        visit_repo: Optional[VisitRepository] = None,
    ):
        self._visitor_repo = visitor_repo
        self._event_repo = event_repo
        self._visit_repo = visit_repo

    @property
    def is_available(self) -> bool:
        return bool(
            self._visitor_repo
            and self._visitor_repo.is_available
            and self._event_repo
            and self._event_repo.is_available
            and self._visit_repo
            and self._visit_repo.is_available
        )

    async def record_movement_event(
        self,
        venue_id: str,
        session_id: str,
        visitor_id: str,
        event_type: str,
        gate_id: str,
        timestamp: Union[datetime, str, None] = None,
        source_event_id: Optional[str] = None,
        visitor_event_id: Optional[str] = None,
        track_id: Optional[str] = None,
        camera_id: Optional[str] = None,
        dwell_time: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record a movement event (ENTRY or EXIT) for a visitor in a venue.

        CTO Constraints:
        1. total_visits semantics:
           - ENTRY that opens a visit -> total_visits += 1
           - EXIT -> does NOT increment total_visits
           - Consecutive ENTRY with existing OPEN visit -> total_visits NOT incremented
        2. Idempotency:
           - Duplicate source_event_id or visitor_event_id is checked and suppressed without duplicate history
        3. Consecutive ENTRY (Sprint 6 aligned):
           - Preserves physical event in visitor_events
           - Existing OPEN visit remains unclosed; no fake exit or fabricated duration
        4. Concurrency:
           - Visit completion is atomic; at most one OPEN visit per (venue_id, visitor_id)
        5. Venue isolation:
           - All operations strictly scoped by venue_id and visitor_id
        """
        event_type = event_type.upper()
        utc_dt = ensure_utc_datetime(timestamp) or datetime.now(timezone.utc)

        # 1. Idempotency check: duplicate visitor_event_id if provided
        if visitor_event_id and self._event_repo and self._event_repo.is_available:
            existing_vid = await self._event_repo.get_by_event_id(visitor_event_id)
            if existing_vid:
                logger.info(
                    f"Idempotent event suppressed: visitor_event_id '{visitor_event_id}' already processed."
                )
                return {
                    "status": "ignored",
                    "reason": "duplicate_visitor_event_id",
                    "visitor_event_id": existing_vid.visitor_event_id,
                    "visitor_id": visitor_id,
                }

        # 2. Idempotency check: duplicate source_event_id within venue
        if source_event_id and self._event_repo and self._event_repo.is_available:
            existing_src = await self._event_repo.get_by_source_event_id(venue_id, source_event_id)
            if existing_src:
                logger.info(
                    f"Idempotent event suppressed: source_event_id '{source_event_id}' already processed."
                )
                return {
                    "status": "ignored",
                    "reason": "duplicate_source_event",
                    "visitor_event_id": existing_src.visitor_event_id,
                    "visitor_id": visitor_id,
                }

        visitor_event_id = visitor_event_id or str(uuid.uuid4())

        # Construct immutable event document
        event_doc = VisitorEventDBModel(
            visitor_event_id=visitor_event_id,
            visitor_id=visitor_id,
            venue_id=venue_id,
            session_id=session_id,
            event_type=event_type,
            gate_id=gate_id,
            timestamp=utc_dt,
            source_event_id=source_event_id,
            track_id=track_id,
            camera_id=camera_id,
            dwell_time=dwell_time,
            metadata=metadata or {},
        )

        is_new_visit = False
        visit_record = None

        if event_type == "ENTRY":
            # Check if an OPEN visit already exists for this visitor in this venue
            active_visit = None
            if self._visit_repo and self._visit_repo.is_available:
                active_visit = await self._visit_repo.get_active_visit(venue_id, visitor_id)

            if active_visit is None:
                # No active visit -> Create a new OPEN visit
                is_new_visit = True
                new_visit = VisitDBModel(
                    visit_id=str(uuid.uuid4()),
                    visitor_id=visitor_id,
                    venue_id=venue_id,
                    session_id=session_id,
                    entry_event_id=visitor_event_id,
                    entry_time=utc_dt,
                    entry_gate=gate_id,
                    status="OPEN",
                )
                if self._visit_repo and self._visit_repo.is_available:
                    visit_record = await self._visit_repo.create_visit(new_visit)
            else:
                # Active visit already exists (consecutive ENTRY / sensor bounce)
                # Sprint 6 aligned: preserve physical event, keep existing visit OPEN, do not increment total_visits
                logger.info(
                    f"Consecutive ENTRY for visitor '{visitor_id}' in venue '{venue_id}' while visit '{active_visit.visit_id}' is OPEN. Recorded event without duplicate visit."
                )
                is_new_visit = False
                visit_record = active_visit

        elif event_type == "EXIT":
            # Attempt to complete the active OPEN visit atomically
            if self._visit_repo and self._visit_repo.is_available:
                visit_record = await self._visit_repo.complete_visit_atomic(
                    venue_id=venue_id,
                    visitor_id=visitor_id,
                    exit_event_id=visitor_event_id,
                    exit_time=utc_dt,
                    exit_gate=gate_id,
                    dwell_time=dwell_time,
                )

            if not visit_record:
                # EXIT without active OPEN visit: handled safely without fabricating fake entry or duration
                logger.info(
                    f"EXIT event for visitor '{visitor_id}' in venue '{venue_id}' with no active OPEN visit. Physical event recorded (dwell_time=None)."
                )

        # Persist the immutable event record
        if self._event_repo and self._event_repo.is_available:
            await self._event_repo.save_event(event_doc)

        # Update visitor profile with atomic counters (enforcing CTO Constraint 1)
        visitor_profile = None
        if self._visitor_repo and self._visitor_repo.is_available:
            visitor_profile = await self._visitor_repo.upsert_visitor_on_event(
                venue_id=venue_id,
                visitor_id=visitor_id,
                event_type=event_type,
                timestamp=utc_dt,
                is_new_visit=is_new_visit,
                metadata=metadata,
            )

        return {
            "status": "processed",
            "visitor_event_id": visitor_event_id,
            "visitor_id": visitor_id,
            "venue_id": venue_id,
            "event_type": event_type,
            "is_new_visit": is_new_visit,
            "visit_id": visit_record.visit_id if visit_record else None,
            "visitor_profile": visitor_profile.model_dump(mode="json") if visitor_profile else None,
        }

    async def get_visitor_profile(self, venue_id: str, visitor_id: str) -> VisitorResponse:
        """Fetch visitor profile scoped strictly by venue_id and visitor_id."""
        if not self._visitor_repo or not self._visitor_repo.is_available:
            raise NotFoundException(f"Visitor '{visitor_id}' not found in venue '{venue_id}' (db unavailable).")

        visitor = await self._visitor_repo.get_by_venue_and_visitor(venue_id, visitor_id)
        if not visitor:
            raise NotFoundException(f"Visitor '{visitor_id}' not found in venue '{venue_id}'.")

        return VisitorResponse(
            visitor_id=visitor.visitor_id,
            venue_id=visitor.venue_id,
            first_seen=_format_iso(visitor.first_seen_at),
            last_seen=_format_iso(visitor.last_seen_at),
            total_entries=visitor.total_entries,
            total_exits=visitor.total_exits,
            total_visits=visitor.total_visits,
            metadata=visitor.metadata or {},
        )

    async def get_visitor_events(
        self,
        venue_id: str,
        visitor_id: str,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> VisitorEventsListResponse:
        """Get paginated chronological movement events timeline for a visitor."""
        limit = min(max(1, limit), 200)
        skip = max(0, skip)

        dt_start = parse_query_timestamp(start_time, is_end_of_day=False)
        dt_end = parse_query_timestamp(end_time, is_end_of_day=True)

        if not self._event_repo or not self._event_repo.is_available:
            return VisitorEventsListResponse(
                visitor_id=visitor_id,
                venue_id=venue_id,
                total=0,
                limit=limit,
                skip=skip,
                events=[],
            )

        events = await self._event_repo.list_events_by_visitor(
            venue_id=venue_id,
            visitor_id=visitor_id,
            start_time=dt_start,
            end_time=dt_end,
            event_type=event_type,
            limit=limit,
            skip=skip,
        )
        total = await self._event_repo.count_events(
            venue_id=venue_id,
            visitor_id=visitor_id,
            start_time=dt_start,
            end_time=dt_end,
            event_type=event_type,
        )

        items = [
            VisitorEventItem(
                visitor_event_id=e.visitor_event_id,
                visitor_id=e.visitor_id,
                venue_id=e.venue_id,
                session_id=e.session_id,
                event_type=e.event_type,
                gate_id=e.gate_id,
                timestamp=_format_iso(e.timestamp),
                source_event_id=e.source_event_id,
                track_id=e.track_id,
                camera_id=e.camera_id,
                dwell_time=e.dwell_time,
            )
            for e in events
        ]

        return VisitorEventsListResponse(
            visitor_id=visitor_id,
            venue_id=venue_id,
            total=total,
            limit=limit,
            skip=skip,
            events=items,
        )

    async def get_visitor_visits(
        self,
        venue_id: str,
        visitor_id: str,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> VisitsListResponse:
        """Get paginated visits history for a visitor."""
        limit = min(max(1, limit), 200)
        skip = max(0, skip)

        dt_start = parse_query_timestamp(start_time, is_end_of_day=False)
        dt_end = parse_query_timestamp(end_time, is_end_of_day=True)

        if not self._visit_repo or not self._visit_repo.is_available:
            return VisitsListResponse(
                visitor_id=visitor_id,
                venue_id=venue_id,
                total=0,
                limit=limit,
                skip=skip,
                visits=[],
            )

        visits = await self._visit_repo.list_visits_by_visitor(
            venue_id=venue_id,
            visitor_id=visitor_id,
            start_time=dt_start,
            end_time=dt_end,
            status=status,
            limit=limit,
            skip=skip,
        )
        total = await self._visit_repo.count_visits(
            venue_id=venue_id,
            visitor_id=visitor_id,
            start_time=dt_start,
            end_time=dt_end,
            status=status,
        )

        items = [
            VisitItem(
                visit_id=v.visit_id,
                visitor_id=v.visitor_id,
                venue_id=v.venue_id,
                session_id=v.session_id,
                entry_event_id=v.entry_event_id,
                exit_event_id=v.exit_event_id,
                entry_time=_format_iso(v.entry_time),
                exit_time=_format_iso(v.exit_time),
                entry_gate=v.entry_gate,
                exit_gate=v.exit_gate,
                duration_seconds=v.duration_seconds,
                status=v.status,
            )
            for v in visits
        ]

        return VisitsListResponse(
            visitor_id=visitor_id,
            venue_id=venue_id,
            total=total,
            limit=limit,
            skip=skip,
            visits=items,
        )

    async def get_visitor_history(
        self,
        venue_id: str,
        visitor_id: str,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
        limit: int = 50,
    ) -> VisitorHistoryResponse:
        """Get consolidated visitor summary, recent visits, and recent movement events."""
        profile = await self.get_visitor_profile(venue_id=venue_id, visitor_id=visitor_id)
        visits_resp = await self.get_visitor_visits(
            venue_id=venue_id,
            visitor_id=visitor_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            skip=0,
        )
        events_resp = await self.get_visitor_events(
            venue_id=venue_id,
            visitor_id=visitor_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            skip=0,
        )

        return VisitorHistoryResponse(
            visitor=profile,
            recent_visits=visits_resp.visits,
            recent_events=events_resp.events,
        )

    async def apply_retention_policy(self, cutoff: datetime, venue_id: Optional[str] = None) -> Dict[str, int]:
        """
        Explicit maintenance retention purge: delete records with timestamps older than cutoff.
        Never invoked during normal event ingestion.
        """
        deleted_events = 0
        deleted_visits = 0
        deleted_visitors = 0

        if self._event_repo and self._event_repo.is_available:
            deleted_events = await self._event_repo.delete_older_than(cutoff, venue_id=venue_id)
        if self._visit_repo and self._visit_repo.is_available:
            deleted_visits = await self._visit_repo.delete_older_than(cutoff, venue_id=venue_id)
        if self._visitor_repo and self._visitor_repo.is_available:
            deleted_visitors = await self._visitor_repo.delete_older_than(cutoff, venue_id=venue_id)

        return {
            "deleted_events": deleted_events,
            "deleted_visits": deleted_visits,
            "deleted_visitors": deleted_visitors,
        }

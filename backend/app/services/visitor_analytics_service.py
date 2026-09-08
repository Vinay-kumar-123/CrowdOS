"""
Visitor Analytics Service — Sprint 14.

Coordinates historical visitor intelligence across:
- Visitor profile analytics & durations
- Gate usage analytics with deterministic tie-breaking
- Day-by-day visitor metrics
- Chronological multi-visit daily timeline
- Visit frequency & returning visitor classification
- Venue-wide visitor analytics & new vs returning breakdown
- Venue-wide daily trend trajectories

Enforces strict venue isolation, UTC timestamp normalization,
invalid range rejection, and degraded database mode safety.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Union

from app.models.visitor import ensure_utc_datetime
from app.repositories.visitor_analytics_repository import VisitorAnalyticsRepository
from app.schemas.visitor_analytics import (
    VisitorAnalyticsSummaryResponse,
    VisitorDailyAnalyticsListResponse,
    VisitorDailyAnalyticsItem,
    VisitorGateAnalyticsResponse,
    GateUsageItem,
    VisitorDurationAnalyticsResponse,
    VisitorTimelineResponse,
    VisitorTimelineDayItem,
    VisitorTimelineVisitItem,
    VisitorFrequencyResponse,
    VenueVisitorAnalyticsResponse,
    VenueDailyTrendsResponse,
    VenueDailyTrendItem,
    VenueAnalyticsSummaryResponse,
)
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    DatabaseConnectionError,
)

logger = logging.getLogger("crowdos.services.visitor_analytics")


def format_utc_iso(dt: Optional[Union[datetime, str]]) -> Optional[str]:
    """Ensure a timestamp is timezone-aware UTC before formatting as ISO 8601."""
    if dt is None:
        return None
    utc_dt = ensure_utc_datetime(dt)
    return utc_dt.isoformat() if utc_dt else None


def parse_and_validate_range(
    start_time: Optional[Union[str, datetime]],
    end_time: Optional[Union[str, datetime]],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Parse query timestamps into timezone-aware UTC datetimes and validate start_time <= end_time.
    Supports YYYY-MM-DD (start of day / end of day) and full ISO 8601 strings.
    Rejects invalid ranges and naive unparseable strings.
    """
    dt_start: Optional[datetime] = None
    dt_end: Optional[datetime] = None

    if start_time is not None:
        if isinstance(start_time, datetime):
            dt_start = start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        else:
            s_str = str(start_time).strip()
            if not s_str:
                dt_start = None
            elif len(s_str) == 10 and s_str.count("-") == 2:
                dt_start = datetime.fromisoformat(f"{s_str}T00:00:00+00:00")
            else:
                try:
                    dt_start = ensure_utc_datetime(s_str)
                except Exception as e:
                    raise ValidationException(f"Invalid start_time format: '{start_time}'. Must be ISO 8601 or YYYY-MM-DD.") from e
                if dt_start is None:
                    raise ValidationException(f"Invalid start_time format: '{start_time}'.")

    if end_time is not None:
        if isinstance(end_time, datetime):
            dt_end = end_time if end_time.tzinfo else end_time.replace(tzinfo=timezone.utc)
        else:
            e_str = str(end_time).strip()
            if not e_str:
                dt_end = None
            elif len(e_str) == 10 and e_str.count("-") == 2:
                dt_end = datetime.fromisoformat(f"{e_str}T23:59:59.999999+00:00")
            else:
                try:
                    dt_end = ensure_utc_datetime(e_str)
                except Exception as e:
                    raise ValidationException(f"Invalid end_time format: '{end_time}'. Must be ISO 8601 or YYYY-MM-DD.") from e
                if dt_end is None:
                    raise ValidationException(f"Invalid end_time format: '{end_time}'.")

    if dt_start and dt_end and dt_start > dt_end:
        raise ValidationException(
            f"Invalid date range: start_time ({dt_start.isoformat()}) must be earlier than or equal to end_time ({dt_end.isoformat()})."
        )

    return dt_start, dt_end


class VisitorAnalyticsService:
    """
    Coordinates historical analytics aggregations and enforces business rules.
    """

    def __init__(self, analytics_repo: VisitorAnalyticsRepository):
        self.repo = analytics_repo

    def _check_db_available(self) -> None:
        """Enforces degraded database mode: never fabricate fake analytics if MongoDB is down."""
        if not self.repo or not self.repo.is_available:
            raise DatabaseConnectionError("Database service unavailable: visitor analytics cannot be computed.")

    # ========================================================================
    # 1. Visitor Profile Summary Analytics
    # ========================================================================

    async def get_visitor_summary(
        self, venue_id: str, visitor_id: str
    ) -> VisitorAnalyticsSummaryResponse:
        """
        Consolidated analytics profile for a specific visitor in a venue.
        Strictly venue-isolated.
        """
        self._check_db_available()

        visitor_doc = await self.repo.get_visitor_profile(venue_id=venue_id, visitor_id=visitor_id)
        if not visitor_doc:
            raise NotFoundException(f"Visitor '{visitor_id}' not found in venue '{venue_id}'.")

        # Duration analytics on completed visits
        duration_stats = await self.repo.get_visit_duration_stats(
            venue_id=venue_id, visitor_id=visitor_id
        )

        # Unique days and bounds
        bounds_stats = await self.repo.get_visitor_visit_days_and_bounds(
            venue_id=venue_id, visitor_id=visitor_id
        )

        # total_visits: authoritative counter from Sprint 13 Visitor profile
        total_visits = visitor_doc.get("total_visits", 0)
        completed_visits = duration_stats["completed_visits_count"]
        open_visits = duration_stats["open_visits_excluded_count"]
        is_returning = total_visits > 1

        first_seen = visitor_doc.get("first_seen_at")
        last_seen = visitor_doc.get("last_seen_at")
        first_visit = bounds_stats.get("first_visit_at")
        last_visit = bounds_stats.get("last_visit_at")

        return VisitorAnalyticsSummaryResponse(
            visitor_id=visitor_id,
            venue_id=venue_id,
            first_seen_at=format_utc_iso(first_seen),
            last_seen_at=format_utc_iso(last_seen),
            total_entries=visitor_doc.get("total_entries", 0),
            total_exits=visitor_doc.get("total_exits", 0),
            total_visits=total_visits,
            completed_visits=completed_visits,
            open_visits=open_visits,
            average_visit_duration_seconds=duration_stats["average_duration_seconds"],
            minimum_visit_duration_seconds=duration_stats["minimum_duration_seconds"],
            maximum_visit_duration_seconds=duration_stats["maximum_duration_seconds"],
            total_visit_duration_seconds=duration_stats["total_duration_seconds"],
            unique_visit_days=bounds_stats["unique_visit_days"],
            first_visit_at=format_utc_iso(first_visit),
            last_visit_at=format_utc_iso(last_visit),
            is_returning_visitor=is_returning,
            metadata=visitor_doc.get("metadata", {}),
        )

    # ========================================================================
    # 2. Daily Visitor Analytics
    # ========================================================================

    async def get_visitor_daily_analytics(
        self,
        venue_id: str,
        visitor_id: str,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
    ) -> VisitorDailyAnalyticsListResponse:
        """Daily movement and presence breakdown for a visitor over a date range."""
        self._check_db_available()
        dt_start, dt_end = parse_and_validate_range(start_time, end_time)

        visitor_doc = await self.repo.get_visitor_profile(venue_id=venue_id, visitor_id=visitor_id)
        if not visitor_doc:
            raise NotFoundException(f"Visitor '{visitor_id}' not found in venue '{venue_id}'.")

        days_data = await self.repo.get_visitor_daily_breakdown(
            venue_id=venue_id, visitor_id=visitor_id, start_time=dt_start, end_time=dt_end
        )

        items = [VisitorDailyAnalyticsItem(**d) for d in days_data]
        return VisitorDailyAnalyticsListResponse(
            visitor_id=visitor_id,
            venue_id=venue_id,
            start_time=dt_start.isoformat() if dt_start else None,
            end_time=dt_end.isoformat() if dt_end else None,
            days=items,
        )

    # ========================================================================
    # 3. Gate Analytics
    # ========================================================================

    async def get_visitor_gate_analytics(
        self,
        venue_id: str,
        visitor_id: Optional[str] = None,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
    ) -> VisitorGateAnalyticsResponse:
        """Gate usage breakdown for a visitor or venue."""
        self._check_db_available()
        dt_start, dt_end = parse_and_validate_range(start_time, end_time)

        if visitor_id:
            visitor_doc = await self.repo.get_visitor_profile(venue_id=venue_id, visitor_id=visitor_id)
            if not visitor_doc:
                raise NotFoundException(f"Visitor '{visitor_id}' not found in venue '{venue_id}'.")

        stats = await self.repo.get_gate_usage_stats(
            venue_id=venue_id,
            visitor_id=visitor_id,
            start_time=dt_start,
            end_time=dt_end,
        )

        entry_items = [GateUsageItem(**g) for g in stats["entry_gates"]]
        exit_items = [GateUsageItem(**g) for g in stats["exit_gates"]]

        return VisitorGateAnalyticsResponse(
            visitor_id=visitor_id,
            venue_id=venue_id,
            total_entries=stats["total_entries"],
            total_exits=stats["total_exits"],
            entry_gates=entry_items,
            exit_gates=exit_items,
            most_used_entry_gate=stats["most_used_entry_gate"],
            most_used_exit_gate=stats["most_used_exit_gate"],
        )

    # ========================================================================
    # 4. Visit Duration Analytics
    # ========================================================================

    async def get_visitor_duration_analytics(
        self,
        venue_id: str,
        visitor_id: Optional[str] = None,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
    ) -> VisitorDurationAnalyticsResponse:
        """Duration statistics for completed visits only."""
        self._check_db_available()
        dt_start, dt_end = parse_and_validate_range(start_time, end_time)

        if visitor_id:
            visitor_doc = await self.repo.get_visitor_profile(venue_id=venue_id, visitor_id=visitor_id)
            if not visitor_doc:
                raise NotFoundException(f"Visitor '{visitor_id}' not found in venue '{venue_id}'.")

        stats = await self.repo.get_visit_duration_stats(
            venue_id=venue_id,
            visitor_id=visitor_id,
            start_time=dt_start,
            end_time=dt_end,
        )

        return VisitorDurationAnalyticsResponse(
            visitor_id=visitor_id,
            venue_id=venue_id,
            completed_visits_count=stats["completed_visits_count"],
            open_visits_excluded_count=stats["open_visits_excluded_count"],
            total_duration_seconds=stats["total_duration_seconds"],
            average_duration_seconds=stats["average_duration_seconds"],
            minimum_duration_seconds=stats["minimum_duration_seconds"],
            maximum_duration_seconds=stats["maximum_duration_seconds"],
            median_duration_seconds=stats["median_duration_seconds"],
        )

    # ========================================================================
    # 5. Visitor Daily Timeline (Multiple Visits Preserved)
    # ========================================================================

    async def get_visitor_timeline(
        self,
        venue_id: str,
        visitor_id: str,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
    ) -> VisitorTimelineResponse:
        """Chronological movement timeline preserving individual visits."""
        self._check_db_available()
        dt_start, dt_end = parse_and_validate_range(start_time, end_time)

        visitor_doc = await self.repo.get_visitor_profile(venue_id=venue_id, visitor_id=visitor_id)
        if not visitor_doc:
            raise NotFoundException(f"Visitor '{visitor_id}' not found in venue '{venue_id}'.")

        timeline_data = await self.repo.get_visitor_timeline(
            venue_id=venue_id,
            visitor_id=visitor_id,
            start_time=dt_start,
            end_time=dt_end,
        )

        days = []
        for d in timeline_data:
            visits = [VisitorTimelineVisitItem(**v) for v in d.get("visits", [])]
            day_node = VisitorTimelineDayItem(
                date=d["date"],
                entries_count=d["entries_count"],
                exits_count=d["exits_count"],
                visits_count=d["visits_count"],
                total_duration_seconds=d["total_duration_seconds"],
                first_event_time=d["first_event_time"],
                last_event_time=d["last_event_time"],
                visits=visits,
            )
            days.append(day_node)

        return VisitorTimelineResponse(
            visitor_id=visitor_id,
            venue_id=venue_id,
            start_time=dt_start.isoformat() if dt_start else None,
            end_time=dt_end.isoformat() if dt_end else None,
            timeline=days,
        )

    # ========================================================================
    # 6. Visitor Frequency & Returning Classification
    # ========================================================================

    async def get_visitor_frequency(
        self, venue_id: str, visitor_id: str
    ) -> VisitorFrequencyResponse:
        """Visit frequency and return patterns for a visitor."""
        self._check_db_available()

        visitor_doc = await self.repo.get_visitor_profile(venue_id=venue_id, visitor_id=visitor_id)
        if not visitor_doc:
            raise NotFoundException(f"Visitor '{visitor_id}' not found in venue '{venue_id}'.")

        bounds = await self.repo.get_visitor_visit_days_and_bounds(venue_id=venue_id, visitor_id=visitor_id)

        total_visits = visitor_doc.get("total_visits", 0)
        unique_active_days = bounds.get("unique_visit_days", 0)
        completed_visits = bounds.get("completed_visits", 0)
        open_visits = bounds.get("open_visits", 0)

        first_seen = visitor_doc.get("first_seen_at")
        days_since_first = 0
        if first_seen:
            now_dt = datetime.now(timezone.utc)
            days_since_first = max(0, (now_dt.date() - first_seen.date()).days)

        span_days = max(1, days_since_first + 1)
        visits_per_day = round(total_visits / span_days, 2)
        avg_visits_per_active = (
            round(total_visits / unique_active_days, 2) if unique_active_days > 0 else 0.0
        )
        is_returning = total_visits > 1

        return VisitorFrequencyResponse(
            visitor_id=visitor_id,
            venue_id=venue_id,
            total_visits=total_visits,
            completed_visits=completed_visits,
            open_visits=open_visits,
            unique_active_days=unique_active_days,
            days_since_first_visit=days_since_first,
            visits_per_day=visits_per_day,
            average_visits_per_active_day=avg_visits_per_active,
            is_returning_visitor=is_returning,
        )

    # ========================================================================
    # 7. Venue-Level Visitor Analytics
    # ========================================================================

    async def get_venue_visitor_analytics(
        self,
        venue_id: str,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
    ) -> VenueVisitorAnalyticsResponse:
        """Venue-level aggregate analytics over a date range."""
        self._check_db_available()
        dt_start, dt_end = parse_and_validate_range(start_time, end_time)

        stats = await self.repo.get_venue_visitor_analytics(
            venue_id=venue_id, start_time=dt_start, end_time=dt_end
        )

        return VenueVisitorAnalyticsResponse(
            venue_id=venue_id,
            start_time=dt_start.isoformat() if dt_start else None,
            end_time=dt_end.isoformat() if dt_end else None,
            unique_visitors=stats["unique_visitors"],
            new_visitors=stats["new_visitors"],
            returning_visitors=stats["returning_visitors"],
            total_entries=stats["total_entries"],
            total_exits=stats["total_exits"],
            total_visits=stats["total_visits"],
            completed_visits=stats["completed_visits"],
            open_visits=stats["open_visits"],
            average_visit_duration_seconds=stats["average_visit_duration_seconds"],
            minimum_visit_duration_seconds=stats["minimum_visit_duration_seconds"],
            maximum_visit_duration_seconds=stats["maximum_visit_duration_seconds"],
            total_visit_duration_seconds=stats["total_visit_duration_seconds"],
        )

    # ========================================================================
    # 8. Venue Daily Trends
    # ========================================================================

    async def get_venue_daily_trends(
        self,
        venue_id: str,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
    ) -> VenueDailyTrendsResponse:
        """Chronological daily trend trajectory for a venue."""
        self._check_db_available()
        dt_start, dt_end = parse_and_validate_range(start_time, end_time)

        trends_data = await self.repo.get_venue_daily_trends(
            venue_id=venue_id, start_time=dt_start, end_time=dt_end
        )

        items = [VenueDailyTrendItem(**t) for t in trends_data]
        return VenueDailyTrendsResponse(
            venue_id=venue_id,
            start_time=dt_start.isoformat() if dt_start else None,
            end_time=dt_end.isoformat() if dt_end else None,
            trends=items,
        )

    # ========================================================================
    # 9. Consolidated Venue Analytics Summary
    # ========================================================================

    async def get_venue_analytics_summary(
        self,
        venue_id: str,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
    ) -> VenueAnalyticsSummaryResponse:
        """Consolidated venue summary combining overview, gate analytics, duration, and daily trends."""
        self._check_db_available()
        dt_start, dt_end = parse_and_validate_range(start_time, end_time)

        overview = await self.get_venue_visitor_analytics(
            venue_id=venue_id, start_time=dt_start, end_time=dt_end
        )
        gate_stats = await self.get_visitor_gate_analytics(
            venue_id=venue_id, visitor_id=None, start_time=dt_start, end_time=dt_end
        )
        duration_stats = await self.get_visitor_duration_analytics(
            venue_id=venue_id, visitor_id=None, start_time=dt_start, end_time=dt_end
        )
        trends_resp = await self.get_venue_daily_trends(
            venue_id=venue_id, start_time=dt_start, end_time=dt_end
        )

        return VenueAnalyticsSummaryResponse(
            overview=overview,
            gate_analytics=gate_stats,
            duration_analytics=duration_stats,
            daily_trends=trends_resp.trends,
        )

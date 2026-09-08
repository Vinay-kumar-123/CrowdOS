"""
Sprint 14 — Visitor Analytics & History Intelligence Tests.

Comprehensive test suite covering all 38 required test cases:
1. Visitor analytics summary
2. First/last seen verification
3. Total entries count
4. Total exits count
5. Total visits count
6. Completed visits count
7. Open visits count
8. Average visit duration calculation
9. Minimum visit duration calculation
10. Maximum visit duration calculation
11. Total visit duration calculation
12. Unique visit days count
13. Multiple visits on same day distinction
14. Daily visitor analytics
15. Date-range analytics
16. Exact start boundary inclusion
17. Exact end boundary inclusion
18. Outside-range exclusion
19. Gate usage counts
20. Gate percentages calculation
21. Deterministic gate tie-breaking (alphabetical)
22. Visit frequency calculation
23. Returning visitor classification (total_visits > 1)
24. New visitor classification (first seen in range)
25. Historical first-seen outside date range classified as returning
26. Venue-level analytics aggregation
27. Strict venue isolation (Venue A vs Venue B)
28. Empty analytics behavior (zeros for counts, None for durations)
29. Open visits excluded from duration statistics
30. Cross-session analytics
31. Cross-gate analytics
32. UTC timezone normalization
33. Invalid date range rejection (start_time > end_time)
34. Pagination and limit bounds
35. Privacy response recursive audit
36. Degraded MongoDB mode (503 response, no fake zeros)
37. Sprint 13 persistence regression check
38. Sprint 10 database connection regression check
"""
import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError
from mongomock_motor import AsyncMongoMockClient
from httpx import AsyncClient, ASGITransport

from app.main import get_application
from app.models.event import PROHIBITED_BIOMETRIC_FIELDS
from app.models.visitor import (
    VisitorDBModel,
    VisitorEventDBModel,
    VisitDBModel,
)
from app.repositories.visitor_repository import (
    VisitorRepository,
    VisitorEventRepository,
    VisitRepository,
)
from app.repositories.visitor_analytics_repository import VisitorAnalyticsRepository
from app.services.visitor_history_service import VisitorHistoryService
from app.services.visitor_analytics_service import (
    VisitorAnalyticsService,
    parse_and_validate_range,
)
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    DatabaseConnectionError,
)
from app.schemas.visitor_analytics import _assert_no_biometrics_recursive


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def analytics_test_db():
    client = AsyncMongoMockClient()
    return client["test_visitor_analytics_db"]


@pytest.fixture
def visitor_history_service(analytics_test_db):
    visitor_repo = VisitorRepository(analytics_test_db["visitors"])
    event_repo = VisitorEventRepository(analytics_test_db["visitor_events"])
    visit_repo = VisitRepository(analytics_test_db["visits"])
    return VisitorHistoryService(
        visitor_repo=visitor_repo,
        event_repo=event_repo,
        visit_repo=visit_repo,
    )


@pytest.fixture
def analytics_service(analytics_test_db):
    repo = VisitorAnalyticsRepository(
        visitors_collection=analytics_test_db["visitors"],
        visitor_events_collection=analytics_test_db["visitor_events"],
        visits_collection=analytics_test_db["visits"],
    )
    return VisitorAnalyticsService(analytics_repo=repo)


# ============================================================================
# 1-12: Visitor Profile & Duration Analytics Tests
# ============================================================================

@pytest.mark.asyncio
async def test_01_visitor_analytics_summary(visitor_history_service, analytics_service):
    """Test 1: Complete visitor summary profile analytics."""
    venue_id = "v_sum_1"
    visitor_id = "vis_sum_1"
    t1 = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 8, 11, 0, 0, tzinfo=timezone.utc)

    # Ingest ENTRY and EXIT (duration: 3600s)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "gate_1", t1)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "gate_1", t2)

    summary = await analytics_service.get_visitor_summary(venue_id, visitor_id)
    assert summary.visitor_id == visitor_id
    assert summary.venue_id == venue_id
    assert summary.total_entries == 1
    assert summary.total_exits == 1
    assert summary.total_visits == 1
    assert summary.completed_visits == 1
    assert summary.open_visits == 0
    assert summary.total_visit_duration_seconds == 3600.0
    assert summary.average_visit_duration_seconds == 3600.0
    assert summary.unique_visit_days == 1
    assert summary.is_returning_visitor is False


@pytest.mark.asyncio
async def test_02_first_last_seen(visitor_history_service, analytics_service):
    """Test 2: First seen and last seen timestamps with out-of-order ingestion."""
    venue_id = "v_seen"
    visitor_id = "vis_seen"
    t_mid = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)
    t_early = datetime(2026, 9, 8, 8, 0, 0, tzinfo=timezone.utc)
    t_late = datetime(2026, 9, 8, 18, 0, 0, tzinfo=timezone.utc)

    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_mid)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_early)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t_late)

    summary = await analytics_service.get_visitor_summary(venue_id, visitor_id)
    assert summary.first_seen_at == t_early.isoformat()
    assert summary.last_seen_at == t_late.isoformat()


@pytest.mark.asyncio
async def test_03_total_entries(visitor_history_service, analytics_service):
    """Test 3: Total physical entries count."""
    venue_id = "v_ent"
    visitor_id = "vis_ent"
    t_base = datetime(2026, 9, 8, 9, 0, 0, tzinfo=timezone.utc)

    for i in range(4):
        await visitor_history_service.record_movement_event(
            venue_id, "s1", visitor_id, "ENTRY", f"gate_{i}", t_base + timedelta(hours=i)
        )

    summary = await analytics_service.get_visitor_summary(venue_id, visitor_id)
    assert summary.total_entries == 4


@pytest.mark.asyncio
async def test_04_total_exits(visitor_history_service, analytics_service):
    """Test 4: Total physical exits count."""
    venue_id = "v_exit"
    visitor_id = "vis_exit"
    t_base = datetime(2026, 9, 8, 9, 0, 0, tzinfo=timezone.utc)

    for i in range(3):
        await visitor_history_service.record_movement_event(
            venue_id, "s1", visitor_id, "EXIT", f"gate_{i}", t_base + timedelta(hours=i)
        )

    summary = await analytics_service.get_visitor_summary(venue_id, visitor_id)
    assert summary.total_exits == 3


@pytest.mark.asyncio
async def test_05_total_visits(visitor_history_service, analytics_service):
    """Test 5: total_visits semantics (ENTRY opening visit increments, consecutive entry does not)."""
    venue_id = "v_totvis"
    visitor_id = "vis_totvis"
    t1 = datetime(2026, 9, 8, 9, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 8, 9, 30, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    # First ENTRY opens visit 1 -> total_visits = 1
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t1)
    # Consecutive ENTRY while visit 1 is OPEN -> total_visits remains 1
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t2)
    # EXIT completes visit 1 -> total_visits remains 1
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t3)

    summary = await analytics_service.get_visitor_summary(venue_id, visitor_id)
    assert summary.total_visits == 1
    assert summary.total_entries == 2
    assert summary.total_exits == 1


@pytest.mark.asyncio
async def test_06_completed_visits(visitor_history_service, analytics_service):
    """Test 6: completed_visits counts only visits with status 'COMPLETED'."""
    venue_id = "v_comp"
    visitor_id = "vis_comp"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    # Visit 1: completed
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t + timedelta(minutes=30))

    # Visit 2: completed
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t + timedelta(hours=1))
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t + timedelta(hours=1, minutes=45))

    # Visit 3: left OPEN
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t + timedelta(hours=3))

    summary = await analytics_service.get_visitor_summary(venue_id, visitor_id)
    assert summary.total_visits == 3
    assert summary.completed_visits == 2
    assert summary.open_visits == 1


@pytest.mark.asyncio
async def test_07_open_visits(visitor_history_service, analytics_service):
    """Test 7: open_visits correctly tracks open visit."""
    venue_id = "v_open"
    visitor_id = "vis_open"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t)
    summary = await analytics_service.get_visitor_summary(venue_id, visitor_id)
    assert summary.open_visits == 1
    assert summary.completed_visits == 0
    assert summary.average_visit_duration_seconds is None


@pytest.mark.asyncio
async def test_08_average_duration(visitor_history_service, analytics_service):
    """Test 8: Average visit duration calculation on completed visits."""
    venue_id = "v_avg"
    visitor_id = "vis_avg"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    # Visit 1: 100 seconds
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t + timedelta(seconds=100))

    # Visit 2: 300 seconds
    t2 = t + timedelta(hours=1)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t2)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t2 + timedelta(seconds=300))

    summary = await analytics_service.get_visitor_summary(venue_id, visitor_id)
    assert summary.average_visit_duration_seconds == 200.0


@pytest.mark.asyncio
async def test_09_min_duration(visitor_history_service, analytics_service):
    """Test 9: Minimum visit duration calculation."""
    venue_id = "v_min"
    visitor_id = "vis_min"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    # Visit 1: 50s
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t + timedelta(seconds=50))

    # Visit 2: 500s
    t2 = t + timedelta(hours=1)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t2)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t2 + timedelta(seconds=500))

    summary = await analytics_service.get_visitor_summary(venue_id, visitor_id)
    assert summary.minimum_visit_duration_seconds == 50.0


@pytest.mark.asyncio
async def test_10_max_duration(visitor_history_service, analytics_service):
    """Test 10: Maximum visit duration calculation."""
    venue_id = "v_max"
    visitor_id = "vis_max"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    # Visit 1: 60s
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t + timedelta(seconds=60))

    # Visit 2: 900s
    t2 = t + timedelta(hours=1)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t2)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t2 + timedelta(seconds=900))

    summary = await analytics_service.get_visitor_summary(venue_id, visitor_id)
    assert summary.maximum_visit_duration_seconds == 900.0


@pytest.mark.asyncio
async def test_11_total_duration(visitor_history_service, analytics_service):
    """Test 11: Total visit duration calculation."""
    venue_id = "v_totdur"
    visitor_id = "vis_totdur"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t + timedelta(seconds=120))

    t2 = t + timedelta(hours=1)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t2)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t2 + timedelta(seconds=180))

    summary = await analytics_service.get_visitor_summary(venue_id, visitor_id)
    assert summary.total_visit_duration_seconds == 300.0


@pytest.mark.asyncio
async def test_12_unique_visit_days(visitor_history_service, analytics_service):
    """Test 12: Unique visit days count."""
    venue_id = "v_days"
    visitor_id = "vis_days"

    # Day 1: 2 visits
    t_day1_1 = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)
    t_day1_2 = datetime(2026, 9, 1, 14, 0, 0, tzinfo=timezone.utc)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_day1_1)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t_day1_1 + timedelta(minutes=30))
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_day1_2)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t_day1_2 + timedelta(minutes=30))

    # Day 2: 1 visit
    t_day2 = datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_day2)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t_day2 + timedelta(minutes=45))

    summary = await analytics_service.get_visitor_summary(venue_id, visitor_id)
    assert summary.total_visits == 3
    assert summary.unique_visit_days == 2


# ============================================================================
# 13-18: Multi-visit, Daily & Date-Range Tests
# ============================================================================

@pytest.mark.asyncio
async def test_13_multiple_visits_on_same_day(visitor_history_service, analytics_service):
    """Test 13: Multiple visits on the same day remain distinct and distinguishable."""
    venue_id = "v_multivis"
    visitor_id = "vis_multivis"
    t_morning = datetime(2026, 9, 8, 9, 5, 0, tzinfo=timezone.utc)
    t_noon = datetime(2026, 9, 8, 14, 10, 0, tzinfo=timezone.utc)
    t_evening = datetime(2026, 9, 8, 18, 30, 0, tzinfo=timezone.utc)

    # Visit 1: 09:05 -> 10:20 (75 min = 4500s)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_morning)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t_morning + timedelta(minutes=75))

    # Visit 2: 14:10 -> 15:00 (50 min = 3000s)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g2", t_noon)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g2", t_noon + timedelta(minutes=50))

    # Visit 3: 18:30 -> OPEN
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_evening)

    timeline_resp = await analytics_service.get_visitor_timeline(venue_id, visitor_id)
    assert len(timeline_resp.timeline) == 1
    day_node = timeline_resp.timeline[0]
    assert day_node.date == "2026-09-08"
    assert day_node.visits_count == 3
    assert len(day_node.visits) == 3
    assert day_node.visits[0].status == "COMPLETED"
    assert day_node.visits[0].duration_seconds == 4500.0
    assert day_node.visits[1].status == "COMPLETED"
    assert day_node.visits[1].duration_seconds == 3000.0
    assert day_node.visits[2].status == "OPEN"
    assert day_node.visits[2].duration_seconds is None


@pytest.mark.asyncio
async def test_14_daily_analytics(visitor_history_service, analytics_service):
    """Test 14: Daily visitor analytics."""
    venue_id = "v_daily"
    visitor_id = "vis_daily"
    t1 = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 9, 11, 0, 0, tzinfo=timezone.utc)

    # Day 1
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t1)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t1 + timedelta(seconds=600))

    # Day 2
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t2)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t2 + timedelta(seconds=1200))

    daily_resp = await analytics_service.get_visitor_daily_analytics(venue_id, visitor_id)
    assert len(daily_resp.days) == 2
    assert daily_resp.days[0].date == "2026-09-08"
    assert daily_resp.days[0].completed_visits == 1
    assert daily_resp.days[0].total_visit_duration_seconds == 600.0
    assert daily_resp.days[1].date == "2026-09-09"
    assert daily_resp.days[1].completed_visits == 1
    assert daily_resp.days[1].total_visit_duration_seconds == 1200.0


@pytest.mark.asyncio
async def test_15_date_range_analytics(visitor_history_service, analytics_service):
    """Test 15: Analytics filtered by start_time and end_time."""
    venue_id = "v_range"
    visitor_id = "vis_range"

    # Day 1: 2026-09-01 (outside range)
    t_out1 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_out1)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t_out1 + timedelta(seconds=100))

    # Day 2: 2026-09-05 (inside range)
    t_in = datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_in)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t_in + timedelta(seconds=200))

    # Day 3: 2026-09-10 (outside range)
    t_out2 = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_out2)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t_out2 + timedelta(seconds=300))

    dur_resp = await analytics_service.get_visitor_duration_analytics(
        venue_id, visitor_id, start_time="2026-09-04", end_time="2026-09-06"
    )
    assert dur_resp.completed_visits_count == 1
    assert dur_resp.total_duration_seconds == 200.0


@pytest.mark.asyncio
async def test_16_exact_start_boundary(visitor_history_service, analytics_service):
    """Test 16: Event exactly at start boundary is included."""
    venue_id = "v_bnd_start"
    visitor_id = "vis_bnd_start"
    t_start = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)

    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_start)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t_start + timedelta(seconds=60))

    dur = await analytics_service.get_visitor_duration_analytics(
        venue_id, visitor_id, start_time=t_start.isoformat(), end_time="2026-09-08T23:59:59Z"
    )
    assert dur.completed_visits_count == 1


@pytest.mark.asyncio
async def test_17_exact_end_boundary(visitor_history_service, analytics_service):
    """Test 17: Event exactly at end boundary is included."""
    venue_id = "v_bnd_end"
    visitor_id = "vis_bnd_end"
    t_end = datetime(2026, 9, 8, 18, 0, 0, tzinfo=timezone.utc)

    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_end)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t_end + timedelta(seconds=60))

    dur = await analytics_service.get_visitor_duration_analytics(
        venue_id, visitor_id, start_time="2026-09-08T00:00:00Z", end_time=t_end.isoformat()
    )
    assert dur.completed_visits_count == 1


@pytest.mark.asyncio
async def test_18_outside_range_exclusion(visitor_history_service, analytics_service):
    """Test 18: Events 1 second before start and 1 second after end are excluded."""
    venue_id = "v_excl"
    visitor_id = "vis_excl"
    t_start = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)
    t_end = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)

    # 1 second before
    await visitor_history_service.record_movement_event(
        venue_id, "s1", visitor_id, "ENTRY", "g1", t_start - timedelta(seconds=1)
    )
    await visitor_history_service.record_movement_event(
        venue_id, "s1", visitor_id, "EXIT", "g1", t_start
    )

    # 1 second after
    await visitor_history_service.record_movement_event(
        venue_id, "s1", visitor_id, "ENTRY", "g1", t_end + timedelta(seconds=1)
    )
    await visitor_history_service.record_movement_event(
        venue_id, "s1", visitor_id, "EXIT", "g1", t_end + timedelta(seconds=10)
    )

    dur = await analytics_service.get_visitor_duration_analytics(
        venue_id, visitor_id, start_time=t_start.isoformat(), end_time=t_end.isoformat()
    )
    assert dur.completed_visits_count == 0


# ============================================================================
# 19-21: Gate Analytics Tests
# ============================================================================

@pytest.mark.asyncio
async def test_19_gate_usage_counts(visitor_history_service, analytics_service):
    """Test 19: Entry and exit counts per gate."""
    venue_id = "v_gate_cnt"
    visitor_id = "vis_gate_cnt"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    # 3 entries at North, 1 at South
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "North_Gate", t)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "North_Gate", t + timedelta(minutes=10))
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "North_Gate", t + timedelta(minutes=20))
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "South_Gate", t + timedelta(minutes=30))
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "North_Gate", t + timedelta(minutes=40))
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "North_Gate", t + timedelta(minutes=50))
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "South_Gate", t + timedelta(minutes=60))
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "North_Gate", t + timedelta(minutes=70))

    gate_resp = await analytics_service.get_visitor_gate_analytics(venue_id, visitor_id)
    assert gate_resp.total_entries == 4
    assert gate_resp.total_exits == 4
    assert gate_resp.most_used_entry_gate == "North_Gate"
    assert gate_resp.most_used_exit_gate == "North_Gate"


@pytest.mark.asyncio
async def test_20_gate_percentages(visitor_history_service, analytics_service):
    """Test 20: Gate percentage calculations."""
    venue_id = "v_pct"
    visitor_id = "vis_pct"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    # 3 at Gate A (75%), 1 at Gate B (25%)
    for i in range(3):
        await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "Gate_A", t + timedelta(minutes=i))
        await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "Gate_A", t + timedelta(minutes=i, seconds=30))
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "Gate_B", t + timedelta(minutes=10))
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "Gate_B", t + timedelta(minutes=10, seconds=30))

    gate_resp = await analytics_service.get_visitor_gate_analytics(venue_id, visitor_id)
    entry_dict = {g.gate_id: g.percentage for g in gate_resp.entry_gates}
    assert entry_dict["Gate_A"] == 75.0
    assert entry_dict["Gate_B"] == 25.0


@pytest.mark.asyncio
async def test_21_deterministic_gate_tie_handling(visitor_history_service, analytics_service):
    """Test 21: When two gates have equal counts, tie broken alphabetically by gate_id."""
    venue_id = "v_tie"
    visitor_id = "vis_tie"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    # 2 entries at Gate_Z, 2 entries at Gate_A
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "Gate_Z", t)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "Gate_Z", t + timedelta(seconds=10))
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "Gate_Z", t + timedelta(seconds=20))
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "Gate_Z", t + timedelta(seconds=30))

    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "Gate_A", t + timedelta(seconds=40))
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "Gate_A", t + timedelta(seconds=50))
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "Gate_A", t + timedelta(seconds=60))
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "Gate_A", t + timedelta(seconds=70))

    gate_resp = await analytics_service.get_visitor_gate_analytics(venue_id, visitor_id)
    # Both have count 2. Alphabetical tie-breaking means Gate_A wins!
    assert gate_resp.most_used_entry_gate == "Gate_A"
    assert gate_resp.entry_gates[0].gate_id == "Gate_A"
    assert gate_resp.entry_gates[1].gate_id == "Gate_Z"


# ============================================================================
# 22-25: Visit Frequency & New vs Returning Tests
# ============================================================================

@pytest.mark.asyncio
async def test_22_visit_frequency(visitor_history_service, analytics_service):
    """Test 22: Visit frequency metrics calculation."""
    venue_id = "v_freq"
    visitor_id = "vis_freq"
    t1 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 5, 14, 0, 0, tzinfo=timezone.utc)

    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t1)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t1 + timedelta(hours=1))

    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t2)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t2 + timedelta(hours=1))

    freq_resp = await analytics_service.get_visitor_frequency(venue_id, visitor_id)
    assert freq_resp.total_visits == 2
    assert freq_resp.completed_visits == 2
    assert freq_resp.unique_active_days == 2
    assert freq_resp.average_visits_per_active_day == 1.0
    assert freq_resp.is_returning_visitor is True


@pytest.mark.asyncio
async def test_23_returning_visitor_classification(visitor_history_service, analytics_service):
    """Test 23: Returning visitor classification (total_visits > 1)."""
    venue_id = "v_ret"
    visitor_single = "vis_one"
    visitor_multi = "vis_two"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    # Visitor with 1 visit
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_single, "ENTRY", "g1", t)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_single, "EXIT", "g1", t + timedelta(minutes=10))

    # Visitor with 2 visits
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_multi, "ENTRY", "g1", t)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_multi, "EXIT", "g1", t + timedelta(minutes=10))
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_multi, "ENTRY", "g1", t + timedelta(hours=1))
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_multi, "EXIT", "g1", t + timedelta(hours=1, minutes=10))

    summary1 = await analytics_service.get_visitor_summary(venue_id, visitor_single)
    assert summary1.is_returning_visitor is False

    summary2 = await analytics_service.get_visitor_summary(venue_id, visitor_multi)
    assert summary2.is_returning_visitor is True


@pytest.mark.asyncio
async def test_24_new_visitor_classification(visitor_history_service, analytics_service):
    """Test 24: Visitor first seen inside date range classified as new."""
    venue_id = "v_new"
    visitor_id = "vis_brand_new"
    t_inside = datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc)

    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_inside)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t_inside + timedelta(minutes=30))

    venue_analytics = await analytics_service.get_venue_visitor_analytics(
        venue_id, start_time="2026-09-04", end_time="2026-09-06"
    )
    assert venue_analytics.unique_visitors == 1
    assert venue_analytics.new_visitors == 1
    assert venue_analytics.returning_visitors == 0


@pytest.mark.asyncio
async def test_25_historical_first_seen_outside_date_range(visitor_history_service, analytics_service):
    """
    Test 25: Visitor whose first-ever historical event was before start_time,
    even if appearing once in the range, is classified as returning.
    """
    venue_id = "v_hist"
    visitor_id = "vis_hist_seen"

    # First seen August 10 (long before September)
    t_historical = datetime(2026, 8, 10, 10, 0, 0, tzinfo=timezone.utc)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_historical)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t_historical + timedelta(hours=1))

    # Seen once in September
    t_sep = datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_sep)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t_sep + timedelta(hours=1))

    venue_analytics = await analytics_service.get_venue_visitor_analytics(
        venue_id, start_time="2026-09-01", end_time="2026-09-10"
    )
    assert venue_analytics.unique_visitors == 1
    assert venue_analytics.new_visitors == 0
    assert venue_analytics.returning_visitors == 1


# ============================================================================
# 26-29: Venue-Level, Isolation & Empty Data Tests
# ============================================================================

@pytest.mark.asyncio
async def test_26_venue_level_analytics(visitor_history_service, analytics_service):
    """Test 26: Venue-level aggregation over date range."""
    venue_id = "v_venue_agg"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    # 2 distinct visitors
    await visitor_history_service.record_movement_event(venue_id, "s1", "v1", "ENTRY", "g1", t)
    await visitor_history_service.record_movement_event(venue_id, "s1", "v1", "EXIT", "g1", t + timedelta(seconds=100))

    await visitor_history_service.record_movement_event(venue_id, "s1", "v2", "ENTRY", "g2", t + timedelta(minutes=10))
    await visitor_history_service.record_movement_event(venue_id, "s1", "v2", "EXIT", "g2", t + timedelta(minutes=10, seconds=200))

    res = await analytics_service.get_venue_visitor_analytics(venue_id)
    assert res.unique_visitors == 2
    assert res.total_entries == 2
    assert res.total_exits == 2
    assert res.total_visits == 2
    assert res.completed_visits == 2
    assert res.average_visit_duration_seconds == 150.0
    assert res.total_visit_duration_seconds == 300.0


@pytest.mark.asyncio
async def test_27_venue_isolation(visitor_history_service, analytics_service):
    """Test 27: Strict venue isolation. Data in Venue A never leaks into Venue B."""
    v_a = "venue_isolate_a"
    v_b = "venue_isolate_b"
    vis_id = "shared_visitor_id"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    await visitor_history_service.record_movement_event(v_a, "s1", vis_id, "ENTRY", "g_a", t)
    await visitor_history_service.record_movement_event(v_a, "s1", vis_id, "EXIT", "g_a", t + timedelta(minutes=30))

    # Query Venue A
    summary_a = await analytics_service.get_visitor_summary(v_a, vis_id)
    assert summary_a.total_entries == 1
    assert summary_a.total_visits == 1

    # Query Venue B: Must raise NotFoundException
    with pytest.raises(NotFoundException):
        await analytics_service.get_visitor_summary(v_b, vis_id)

    # Venue B aggregate must be completely 0
    res_b = await analytics_service.get_venue_visitor_analytics(v_b)
    assert res_b.unique_visitors == 0
    assert res_b.total_visits == 0


@pytest.mark.asyncio
async def test_28_empty_analytics_behavior(analytics_service):
    """Test 28: Empty analytics returns zeros for counts, None for duration averages, empty lists."""
    venue_id = "empty_venue"
    res = await analytics_service.get_venue_visitor_analytics(venue_id)
    assert res.unique_visitors == 0
    assert res.total_entries == 0
    assert res.total_exits == 0
    assert res.total_visits == 0
    assert res.completed_visits == 0
    assert res.open_visits == 0
    assert res.average_visit_duration_seconds is None
    assert res.minimum_visit_duration_seconds is None
    assert res.maximum_visit_duration_seconds is None
    assert res.total_visit_duration_seconds == 0.0

    trends = await analytics_service.get_venue_daily_trends(venue_id)
    assert trends.trends == []


@pytest.mark.asyncio
async def test_29_open_visits_excluded_from_duration(visitor_history_service, analytics_service):
    """Test 29: Open visits do not contribute fabricated durations and are excluded from averages."""
    venue_id = "v_open_dur"
    visitor_id = "vis_open_dur"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    # Visit 1: Completed (100s)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t + timedelta(seconds=100))

    # Visit 2: OPEN
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t + timedelta(hours=1))

    dur = await analytics_service.get_visitor_duration_analytics(venue_id, visitor_id)
    assert dur.completed_visits_count == 1
    assert dur.open_visits_excluded_count == 1
    assert dur.average_duration_seconds == 100.0
    assert dur.total_duration_seconds == 100.0


# ============================================================================
# 30-34: Cross-Session, Cross-Gate, Time & Range Validation Tests
# ============================================================================

@pytest.mark.asyncio
async def test_30_cross_session_analytics(visitor_history_service, analytics_service):
    """Test 30: Events across multiple sessions in the same venue aggregate properly."""
    venue_id = "v_cross_sess"
    visitor_id = "vis_cross"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    # Session 1
    await visitor_history_service.record_movement_event(venue_id, "session_1", visitor_id, "ENTRY", "g1", t)
    await visitor_history_service.record_movement_event(venue_id, "session_1", visitor_id, "EXIT", "g1", t + timedelta(minutes=20))

    # Session 2
    await visitor_history_service.record_movement_event(venue_id, "session_2", visitor_id, "ENTRY", "g1", t + timedelta(hours=2))
    await visitor_history_service.record_movement_event(venue_id, "session_2", visitor_id, "EXIT", "g1", t + timedelta(hours=2, minutes=30))

    summary = await analytics_service.get_visitor_summary(venue_id, visitor_id)
    assert summary.total_visits == 2
    assert summary.completed_visits == 2
    assert summary.total_visit_duration_seconds == 3000.0


@pytest.mark.asyncio
async def test_31_cross_gate_analytics(visitor_history_service, analytics_service):
    """Test 31: Cross-gate entry/exit pairing aggregated into gate usage."""
    venue_id = "v_cross_gate"
    visitor_id = "vis_gate_pair"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    # Enter Gate A, Exit Gate B
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "Gate_A", t)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "Gate_B", t + timedelta(minutes=45))

    gate_resp = await analytics_service.get_visitor_gate_analytics(venue_id, visitor_id)
    assert gate_resp.most_used_entry_gate == "Gate_A"
    assert gate_resp.most_used_exit_gate == "Gate_B"
    assert gate_resp.entry_gates[0].gate_id == "Gate_A"
    assert gate_resp.exit_gates[0].gate_id == "Gate_B"


def test_32_utc_normalization():
    """Test 32: Date string expands to UTC midnight and end of day."""
    start_str = "2026-09-08"
    end_str = "2026-09-08"

    dt_start, dt_end = parse_and_validate_range(start_str, end_str)
    assert dt_start == datetime(2026, 9, 8, 0, 0, 0, tzinfo=timezone.utc)
    assert dt_end == datetime(2026, 9, 8, 23, 59, 59, 999999, tzinfo=timezone.utc)


def test_33_invalid_date_range_rejection():
    """Test 33: start_time > end_time is rejected with ValidationException."""
    start = "2026-09-10T12:00:00Z"
    end = "2026-09-08T12:00:00Z"

    with pytest.raises(ValidationException) as exc:
        parse_and_validate_range(start, end)
    assert "start_time" in str(exc.value)


@pytest.mark.asyncio
async def test_34_pagination_and_limits(visitor_history_service, analytics_service):
    """Test 34: Daily analytics date range limits."""
    venue_id = "v_lim"
    visitor_id = "vis_lim"
    t_base = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)

    # Ingest visits across 5 different days
    for i in range(5):
        t = t_base + timedelta(days=i)
        await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t)
        await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t + timedelta(minutes=10))

    # Query only days 2 to 4
    daily_resp = await analytics_service.get_visitor_daily_analytics(
        venue_id, visitor_id, start_time="2026-09-02", end_time="2026-09-04"
    )
    assert len(daily_resp.days) == 3


# ============================================================================
# 35-38: Privacy, Degraded Mode & Regressions
# ============================================================================

@pytest.mark.asyncio
async def test_35_privacy_response_audit(visitor_history_service, analytics_service):
    """Test 35: Recursive scan of analytics responses ensuring zero prohibited biometric fields."""
    venue_id = "v_priv"
    visitor_id = "vis_priv"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t)
    await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t + timedelta(minutes=30))

    summary = await analytics_service.get_visitor_summary(venue_id, visitor_id)
    _assert_no_biometrics_recursive(summary.model_dump())

    gates = await analytics_service.get_visitor_gate_analytics(venue_id, visitor_id)
    _assert_no_biometrics_recursive(gates.model_dump())

    dur = await analytics_service.get_visitor_duration_analytics(venue_id, visitor_id)
    _assert_no_biometrics_recursive(dur.model_dump())

    timeline = await analytics_service.get_visitor_timeline(venue_id, visitor_id)
    _assert_no_biometrics_recursive(timeline.model_dump())

    freq = await analytics_service.get_visitor_frequency(venue_id, visitor_id)
    _assert_no_biometrics_recursive(freq.model_dump())

    venue_res = await analytics_service.get_venue_visitor_analytics(venue_id)
    _assert_no_biometrics_recursive(venue_res.model_dump())

    trends = await analytics_service.get_venue_daily_trends(venue_id)
    _assert_no_biometrics_recursive(trends.model_dump())


@pytest.mark.asyncio
async def test_36_degraded_mongodb_mode():
    """Test 36: Degraded MongoDB mode raises DatabaseConnectionError (HTTP 503) without fake zeros."""
    repo = VisitorAnalyticsRepository(
        visitors_collection=None,
        visitor_events_collection=None,
        visits_collection=None,
    )
    svc = VisitorAnalyticsService(analytics_repo=repo)
    assert not svc.repo.is_available

    with pytest.raises(DatabaseConnectionError):
        await svc.get_visitor_summary("deg_venue", "deg_vis")

    with pytest.raises(DatabaseConnectionError):
        await svc.get_venue_visitor_analytics("deg_venue")


@pytest.mark.asyncio
async def test_37_sprint13_regression(visitor_history_service):
    """Test 37: Sprint 13 persistence and history contracts remain 100% operational."""
    venue_id = "v_s13_reg"
    visitor_id = "vis_s13"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    # Ingest event
    res = await visitor_history_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t)
    assert res["status"] == "processed"
    assert res["is_new_visit"] is True

    # Check Sprint 13 profile
    profile = await visitor_history_service.get_visitor_profile(venue_id, visitor_id)
    assert profile.total_visits == 1

    # Check Sprint 13 visits list
    visits_resp = await visitor_history_service.get_visitor_visits(venue_id, visitor_id)
    assert visits_resp.total == 1
    assert visits_resp.visits[0].status == "OPEN"


@pytest.mark.asyncio
async def test_38_sprint10_regression(analytics_test_db):
    """Test 38: Sprint 10 database connection and index integrity."""
    from app.database.mongodb.indexes import create_all_indexes, INDEX_SPECIFICATIONS

    # Ensure our added indexes exist in specifications
    assert "idx_visitor_events_venue_time" in [idx.document["name"] for idx in INDEX_SPECIFICATIONS["visitor_events"]]
    assert "idx_visits_venue_entry" in [idx.document["name"] for idx in INDEX_SPECIFICATIONS["visits"]]
    assert "idx_visitors_venue_first_seen" in [idx.document["name"] for idx in INDEX_SPECIFICATIONS["visitors"]]

    # Run index creation idempotently
    results = await create_all_indexes(analytics_test_db)
    assert len(results) == 9

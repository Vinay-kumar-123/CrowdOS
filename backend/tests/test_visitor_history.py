"""
Sprint 13 — Visitor Event & History Persistence Layer Tests.

Comprehensive test suite validating:
1. Visitor profile creation, first_seen, last_seen
2. ENTRY & EXIT persistence in visitor_events
3. Visit presence pairing & duration calculation
4. Multiple visits per day (distinct completed visits)
5. Visitor history across multiple sessions within the same venue
6. Cross-gate entry/exit pairing (e.g. enter Gate A, exit Gate B)
7. Idempotency: duplicate visitor_event_id and duplicate source_event_id
8. Consecutive ENTRY with active OPEN visit (Sprint 6 aligned: no duplicate visit, no total_visits increment)
9. Consecutive EXIT / EXIT without active OPEN visit (dwell_time=None, total_exits incremented, no fake visit)
10. ENTRY without EXIT (status='OPEN', duration=None)
11. Out-of-order event timestamps (first_seen = min, last_seen = max)
12. Concurrency safety: atomic visit completion, duplicate OPEN visit prevention
13. Visitor counters: total_entries, total_exits, total_visits (ENTRY only)
14. Historical queries: events, visits, consolidated history, pagination, date boundaries
15. Strict venue isolation: visitor in Venue A cannot be queried or updated under Venue B
16. Strict privacy & biometric ban: rejection of prohibited fields and nested biometrics
17. Degraded MongoDB mode: graceful operation when database is unavailable
18. Retention policy maintenance: deterministic UTC cutoff purge
"""
import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError
from mongomock_motor import AsyncMongoMockClient

from app.models.event import PROHIBITED_BIOMETRIC_FIELDS
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
from app.services.visitor_history_service import (
    VisitorHistoryService,
    parse_query_timestamp,
)
from app.core.exceptions import NotFoundException


# ============================================================================
# 1. Privacy & Biometric Ban Validation
# ============================================================================

def test_visitor_models_reject_all_prohibited_biometric_fields():
    """Verify all 3 models reject prohibited biometric fields."""
    base_visitor = {"visitor_id": "v1", "venue_id": "ven1"}
    base_event = {
        "visitor_event_id": "e1",
        "visitor_id": "v1",
        "venue_id": "ven1",
        "session_id": "s1",
        "event_type": "ENTRY",
        "gate_id": "g1",
        "timestamp": datetime.now(timezone.utc),
    }
    base_visit = {
        "visit_id": "vis1",
        "visitor_id": "v1",
        "venue_id": "ven1",
        "session_id": "s1",
        "entry_event_id": "e1",
        "entry_time": datetime.now(timezone.utc),
        "entry_gate": "g1",
    }

    for prohibited in PROHIBITED_BIOMETRIC_FIELDS:
        # Test VisitorDBModel
        with pytest.raises(ValidationError) as exc:
            VisitorDBModel(**{**base_visitor, prohibited: [0.1, 0.2]})
        assert "PRIVACY VIOLATION" in str(exc.value)

        # Test VisitorEventDBModel
        with pytest.raises(ValidationError) as exc:
            VisitorEventDBModel(**{**base_event, prohibited: "raw_data"})
        assert "PRIVACY VIOLATION" in str(exc.value)

        # Test VisitDBModel
        with pytest.raises(ValidationError) as exc:
            VisitDBModel(**{**base_visit, prohibited: {"vector": 123}})
        assert "PRIVACY VIOLATION" in str(exc.value)


def test_visitor_models_reject_nested_biometric_fields():
    """Verify recursive scanning rejects biometric fields nested inside metadata."""
    with pytest.raises(ValidationError) as exc:
        VisitorDBModel(
            visitor_id="v_nested",
            venue_id="ven1",
            metadata={"deeply": {"nested": {"face_crop": "base64_image"}}},
        )
    assert "PRIVACY VIOLATION" in str(exc.value)


# ============================================================================
# 2. Repository Layer Unit Tests (MongoMock)
# ============================================================================

@pytest.fixture
def repo_test_db():
    client = AsyncMongoMockClient()
    return client["test_visitor_history_db"]


@pytest.mark.asyncio
async def test_visitor_repository_creation_and_counters(repo_test_db):
    """Test VisitorRepository upsert, counter increments, and first/last seen."""
    repo = VisitorRepository(repo_test_db["visitors"])
    t1 = datetime(2026, 9, 8, 9, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)

    # Initial ENTRY with new visit
    v = await repo.upsert_visitor_on_event(
        venue_id="venue_alpha",
        visitor_id="visitor_001",
        event_type="ENTRY",
        timestamp=t1,
        is_new_visit=True,
    )
    assert v.visitor_id == "visitor_001"
    assert v.venue_id == "venue_alpha"
    assert v.total_entries == 1
    assert v.total_exits == 0
    assert v.total_visits == 1
    assert v.first_seen_at == t1
    assert v.last_seen_at == t1

    # Matching EXIT (CTO Constraint 1: EXIT does NOT increment total_visits)
    v2 = await repo.upsert_visitor_on_event(
        venue_id="venue_alpha",
        visitor_id="visitor_001",
        event_type="EXIT",
        timestamp=t2,
        is_new_visit=False,
    )
    assert v2.total_entries == 1
    assert v2.total_exits == 1
    assert v2.total_visits == 1  # unchanged!
    assert v2.first_seen_at == t1
    assert v2.last_seen_at == t2


@pytest.mark.asyncio
async def test_visitor_event_repository_idempotency(repo_test_db):
    """Test that VisitorEventRepository enforces idempotency on visitor_event_id and source_event_id."""
    repo = VisitorEventRepository(repo_test_db["visitor_events"])
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    event1 = VisitorEventDBModel(
        visitor_event_id="evt_uuid_1",
        visitor_id="v1",
        venue_id="ven1",
        session_id="s1",
        event_type="ENTRY",
        gate_id="gate_a",
        timestamp=t,
        source_event_id="source_100",
    )
    saved1 = await repo.save_event(event1)
    assert saved1.visitor_event_id == "evt_uuid_1"

    # Duplicate by visitor_event_id
    saved_dup_id = await repo.save_event(event1)
    assert saved_dup_id.visitor_event_id == "evt_uuid_1"

    # Duplicate by source_event_id with different visitor_event_id
    event2 = VisitorEventDBModel(
        visitor_event_id="evt_uuid_2",
        visitor_id="v1",
        venue_id="ven1",
        session_id="s1",
        event_type="ENTRY",
        gate_id="gate_a",
        timestamp=t,
        source_event_id="source_100",  # SAME source_event_id
    )
    saved_dup_src = await repo.save_event(event2)
    assert saved_dup_src.visitor_event_id == "evt_uuid_1"  # returns original!
    assert await repo.count({"venue_id": "ven1"}) == 1


@pytest.mark.asyncio
async def test_visit_repository_atomic_lifecycle(repo_test_db):
    """Test VisitRepository atomic creation, completion, duration, and double-completion protection."""
    repo = VisitRepository(repo_test_db["visits"])
    t_entry = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)
    t_exit = datetime(2026, 9, 8, 10, 30, 0, tzinfo=timezone.utc)

    # 1. Create OPEN visit
    visit = VisitDBModel(
        visit_id="vis_101",
        visitor_id="v1",
        venue_id="ven1",
        session_id="s1",
        entry_event_id="e_in_1",
        entry_time=t_entry,
        entry_gate="gate_north",
        status="OPEN",
    )
    created = await repo.create_visit(visit)
    assert created.status == "OPEN"

    # Verify active visit lookup
    active = await repo.get_active_visit("ven1", "v1")
    assert active is not None
    assert active.visit_id == "vis_101"

    # 2. Complete visit atomically
    completed = await repo.complete_visit_atomic(
        venue_id="ven1",
        visitor_id="v1",
        exit_event_id="e_out_1",
        exit_time=t_exit,
        exit_gate="gate_south",
    )
    assert completed is not None
    assert completed.status == "COMPLETED"
    assert completed.exit_gate == "gate_south"
    assert completed.duration_seconds == 1800.0  # 30 minutes

    # Active visit is now None
    assert await repo.get_active_visit("ven1", "v1") is None

    # 3. Double-completion protection: second complete attempt returns None
    second_complete = await repo.complete_visit_atomic(
        venue_id="ven1",
        visitor_id="v1",
        exit_event_id="e_out_2",
        exit_time=t_exit,
        exit_gate="gate_south",
    )
    assert second_complete is None


# ============================================================================
# 3. VisitorHistoryService Integrated Scenarios
# ============================================================================

@pytest.fixture
def visitor_service(repo_test_db):
    v_repo = VisitorRepository(repo_test_db["visitors"])
    e_repo = VisitorEventRepository(repo_test_db["visitor_events"])
    vis_repo = VisitRepository(repo_test_db["visits"])
    return VisitorHistoryService(v_repo, e_repo, vis_repo)


@pytest.mark.asyncio
async def test_multiple_visits_in_one_day(visitor_service):
    """
    Test requirement: Multiple visits by the same visitor on the same day
    must create distinct, independent completed visit records.
    """
    venue_id = "stadium_main"
    visitor_id = "fan_777"
    session_id = "game_day_sess"

    # Visit 1: 09:10 to 10:05
    t1_in = datetime(2026, 9, 8, 9, 10, 32, tzinfo=timezone.utc)
    t1_out = datetime(2026, 9, 8, 10, 5, 11, tzinfo=timezone.utc)
    await visitor_service.record_movement_event(venue_id, session_id, visitor_id, "ENTRY", "gate_A", t1_in)
    await visitor_service.record_movement_event(venue_id, session_id, visitor_id, "EXIT", "gate_A", t1_out)

    # Visit 2: 12:30 to 13:20
    t2_in = datetime(2026, 9, 8, 12, 30, 4, tzinfo=timezone.utc)
    t2_out = datetime(2026, 9, 8, 13, 20, 45, tzinfo=timezone.utc)
    await visitor_service.record_movement_event(venue_id, session_id, visitor_id, "ENTRY", "gate_B", t2_in)
    await visitor_service.record_movement_event(venue_id, session_id, visitor_id, "EXIT", "gate_B", t2_out)

    # Visit 3: 17:05 to 18:02
    t3_in = datetime(2026, 9, 8, 17, 5, 10, tzinfo=timezone.utc)
    t3_out = datetime(2026, 9, 8, 18, 2, 33, tzinfo=timezone.utc)
    await visitor_service.record_movement_event(venue_id, session_id, visitor_id, "ENTRY", "gate_A", t3_in)
    await visitor_service.record_movement_event(venue_id, session_id, visitor_id, "EXIT", "gate_C", t3_out)

    # Audit visitor profile
    profile = await visitor_service.get_visitor_profile(venue_id, visitor_id)
    assert profile.total_entries == 3
    assert profile.total_exits == 3
    assert profile.total_visits == 3
    assert profile.first_seen == t1_in.isoformat()
    assert profile.last_seen == t3_out.isoformat()

    # Audit visits list
    visits_resp = await visitor_service.get_visitor_visits(venue_id, visitor_id)
    assert visits_resp.total == 3
    assert len(visits_resp.visits) == 3
    for v in visits_resp.visits:
        assert v.status == "COMPLETED"
        assert v.duration_seconds > 0


@pytest.mark.asyncio
async def test_consecutive_entries_and_exits(visitor_service):
    """
    Test requirement:
    - Consecutive ENTRY while a visit is OPEN (Sprint 6 aligned)
    - Consecutive EXIT / EXIT without active visit
    """
    venue_id = "mall_center"
    visitor_id = "shopper_99"
    session_id = "sess_01"

    t1 = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 8, 10, 5, 0, tzinfo=timezone.utc)  # consecutive entry
    t3 = datetime(2026, 9, 8, 11, 0, 0, tzinfo=timezone.utc)  # exit 1
    t4 = datetime(2026, 9, 8, 11, 5, 0, tzinfo=timezone.utc)  # consecutive exit without open visit

    # Entry 1 -> opens visit
    res1 = await visitor_service.record_movement_event(venue_id, session_id, visitor_id, "ENTRY", "gate_main", t1)
    assert res1["is_new_visit"] is True

    # Entry 2 -> consecutive entry, visit already open
    res2 = await visitor_service.record_movement_event(venue_id, session_id, visitor_id, "ENTRY", "gate_main", t2)
    assert res2["is_new_visit"] is False  # did NOT open a second visit!

    # Profile check: total_entries = 2, total_visits = 1
    p1 = await visitor_service.get_visitor_profile(venue_id, visitor_id)
    assert p1.total_entries == 2
    assert p1.total_visits == 1

    # Exit 1 -> completes the open visit
    await visitor_service.record_movement_event(venue_id, session_id, visitor_id, "EXIT", "gate_main", t3)

    # Exit 2 -> no open visit exists
    await visitor_service.record_movement_event(venue_id, session_id, visitor_id, "EXIT", "gate_main", t4)

    # Profile check: total_exits = 2, total_visits = 1
    p2 = await visitor_service.get_visitor_profile(venue_id, visitor_id)
    assert p2.total_entries == 2
    assert p2.total_exits == 2
    assert p2.total_visits == 1

    # Visits check: exactly 1 visit exists and it is COMPLETED with duration from t1
    visits = await visitor_service.get_visitor_visits(venue_id, visitor_id)
    assert visits.total == 1
    assert visits.visits[0].duration_seconds == 3600.0  # 10:00 to 11:00 = 3600s


@pytest.mark.asyncio
async def test_cross_session_visitor_tracking(visitor_service):
    """Test that a visitor's history spans multiple monitoring sessions in the same venue."""
    venue_id = "terminal_1"
    visitor_id = "traveler_42"

    t1 = datetime(2026, 9, 1, 8, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 8, 14, 0, 0, tzinfo=timezone.utc)

    # Session A (Sept 1)
    await visitor_service.record_movement_event(venue_id, "session_A", visitor_id, "ENTRY", "gate_1", t1)
    await visitor_service.record_movement_event(venue_id, "session_A", visitor_id, "EXIT", "gate_1", t2)

    # Session B (Sept 8)
    await visitor_service.record_movement_event(venue_id, "session_B", visitor_id, "ENTRY", "gate_2", t3)

    profile = await visitor_service.get_visitor_profile(venue_id, visitor_id)
    assert profile.total_entries == 2
    assert profile.total_exits == 1
    assert profile.total_visits == 2
    assert profile.first_seen == t1.isoformat()
    assert profile.last_seen == t3.isoformat()

    # Query events across sessions
    events = await visitor_service.get_visitor_events(venue_id, visitor_id)
    assert events.total == 3
    sessions_found = {e.session_id for e in events.events}
    assert sessions_found == {"session_A", "session_B"}


@pytest.mark.asyncio
async def test_strict_venue_isolation(visitor_service):
    """Test requirement: Visitor data in Venue A is never exposed or conflated with Venue B."""
    v_id = "same_visitor_id"
    t = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)

    # Create event in Venue A
    await visitor_service.record_movement_event("venue_A", "sess_A", v_id, "ENTRY", "gate_A", t)

    # Query Venue A -> found
    p_a = await visitor_service.get_visitor_profile("venue_A", v_id)
    assert p_a.total_entries == 1

    # Query Venue B -> 404 NotFound
    with pytest.raises(NotFoundException):
        await visitor_service.get_visitor_profile("venue_B", v_id)

    # Events in Venue B -> empty
    events_b = await visitor_service.get_visitor_events("venue_B", v_id)
    assert events_b.total == 0
    assert len(events_b.events) == 0


@pytest.mark.asyncio
async def test_retention_purge(visitor_service):
    """Test retention purge of data older than cutoff."""
    venue_id = "retention_venue"
    visitor_id = "old_visitor"
    t_old = datetime(2026, 7, 1, 10, 0, 0, tzinfo=timezone.utc)
    t_new = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)
    cutoff = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)

    # Old event
    await visitor_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_old)
    # New event for different visitor
    await visitor_service.record_movement_event(venue_id, "s2", "new_visitor", "ENTRY", "g1", t_new)

    res = await visitor_service.apply_retention_policy(cutoff=cutoff, venue_id=venue_id)
    assert res["deleted_events"] == 1
    assert res["deleted_visits"] == 1
    assert res["deleted_visitors"] == 1

    # Verify new visitor remains
    p_new = await visitor_service.get_visitor_profile(venue_id, "new_visitor")
    assert p_new.visitor_id == "new_visitor"


# ============================================================================
# 4. End-to-End API Integration Tests (FastAPI Client)
# ============================================================================

@pytest.mark.asyncio
async def test_visitor_api_e2e(async_client):
    """
    Test full REST API lifecycle:
    1. Ingest event via POST /api/v1/venues/{venue_id}/sessions/{session_id}/events with visitor_id
    2. Query GET /api/v1/venues/{venue_id}/visitors/{visitor_id}
    3. Query GET /api/v1/venues/{venue_id}/visitors/{visitor_id}/events
    4. Query GET /api/v1/venues/{venue_id}/visitors/{visitor_id}/visits
    5. Query GET /api/v1/venues/{venue_id}/visitors/{visitor_id}/history
    """
    venue_id = "api_venue_01"
    visitor_id = "vip_guest_999"

    # Start session
    s_res = await async_client.post(f"/api/v1/venues/{venue_id}/sessions", json={"venue_capacity": 5000})
    session_id = s_res.json()["session_id"]
    await async_client.post(f"/api/v1/venues/{venue_id}/sessions/{session_id}/start")

    # Ingest ENTRY with visitor_id
    t_in = "2026-09-08T10:00:00Z"
    in_res = await async_client.post(
        f"/api/v1/venues/{venue_id}/sessions/{session_id}/events",
        json={
            "event_type": "ENTRY",
            "gate_id": "gate_vip_1",
            "timestamp": t_in,
            "visitor_id": visitor_id,
            "event_id": "event_vip_entry",
        },
    )
    assert in_res.status_code == 200

    # Ingest EXIT with visitor_id
    t_out = "2026-09-08T11:15:00Z"
    out_res = await async_client.post(
        f"/api/v1/venues/{venue_id}/sessions/{session_id}/events",
        json={
            "event_type": "EXIT",
            "gate_id": "gate_vip_2",
            "timestamp": t_out,
            "visitor_id": visitor_id,
            "event_id": "event_vip_exit",
            "dwell_time": 4500.0,
        },
    )
    assert out_res.status_code == 200

    # 1. GET Visitor Profile
    prof_res = await async_client.get(f"/api/v1/venues/{venue_id}/visitors/{visitor_id}")
    assert prof_res.status_code == 200
    prof = prof_res.json()
    assert prof["visitor_id"] == visitor_id
    assert prof["venue_id"] == venue_id
    assert prof["total_entries"] == 1
    assert prof["total_exits"] == 1
    assert prof["total_visits"] == 1
    assert "2026-09-08T10:00:00" in prof["first_seen"]
    assert "2026-09-08T11:15:00" in prof["last_seen"]

    # 2. GET Events Timeline
    events_res = await async_client.get(f"/api/v1/venues/{venue_id}/visitors/{visitor_id}/events")
    assert events_res.status_code == 200
    ev_data = events_res.json()
    assert ev_data["total"] == 2
    assert len(ev_data["events"]) == 2
    assert ev_data["events"][0]["event_type"] == "ENTRY"
    assert ev_data["events"][0]["gate_id"] == "gate_vip_1"
    assert ev_data["events"][1]["event_type"] == "EXIT"
    assert ev_data["events"][1]["gate_id"] == "gate_vip_2"

    # 3. GET Visits
    visits_res = await async_client.get(f"/api/v1/venues/{venue_id}/visitors/{visitor_id}/visits")
    assert visits_res.status_code == 200
    vis_data = visits_res.json()
    assert vis_data["total"] == 1
    assert vis_data["visits"][0]["status"] == "COMPLETED"
    assert vis_data["visits"][0]["entry_gate"] == "gate_vip_1"
    assert vis_data["visits"][0]["exit_gate"] == "gate_vip_2"
    assert vis_data["visits"][0]["duration_seconds"] == 4500.0

    # 4. GET Consolidated History
    hist_res = await async_client.get(f"/api/v1/venues/{venue_id}/visitors/{visitor_id}/history")
    assert hist_res.status_code == 200
    hist = hist_res.json()
    assert hist["visitor"]["visitor_id"] == visitor_id
    assert len(hist["recent_visits"]) == 1
    assert len(hist["recent_events"]) == 2


@pytest.mark.asyncio
async def test_visitor_api_isolation_and_404(async_client):
    """Test that requesting an unknown visitor or mismatched venue returns 404."""
    res = await async_client.get("/api/v1/venues/unknown_venue/visitors/unknown_visitor")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_cross_gate_pairing(visitor_service):
    """Test entry at Gate A paired with exit at Gate B."""
    venue_id = "cross_gate_venue"
    visitor_id = "v_cross"
    t_in = datetime(2026, 9, 8, 14, 0, 0, tzinfo=timezone.utc)
    t_out = datetime(2026, 9, 8, 15, 0, 0, tzinfo=timezone.utc)

    await visitor_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "gate_North", t_in)
    await visitor_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "gate_South", t_out)

    visits = await visitor_service.get_visitor_visits(venue_id, visitor_id)
    assert visits.total == 1
    v = visits.visits[0]
    assert v.entry_gate == "gate_North"
    assert v.exit_gate == "gate_South"
    assert v.duration_seconds == 3600.0


@pytest.mark.asyncio
async def test_entry_without_exit_remains_open(visitor_service):
    """Test ENTRY without EXIT leaves visit OPEN with None duration."""
    venue_id = "open_visit_venue"
    visitor_id = "v_open"
    t_in = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    await visitor_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "gate_1", t_in)

    profile = await visitor_service.get_visitor_profile(venue_id, visitor_id)
    assert profile.total_entries == 1
    assert profile.total_exits == 0
    assert profile.total_visits == 1

    visits = await visitor_service.get_visitor_visits(venue_id, visitor_id)
    assert visits.total == 1
    assert visits.visits[0].status == "OPEN"
    assert visits.visits[0].exit_time is None
    assert visits.visits[0].duration_seconds is None


@pytest.mark.asyncio
async def test_out_of_order_event_timestamps(visitor_service):
    """Test that out-of-order events maintain min(first_seen) and max(last_seen)."""
    venue_id = "ooo_venue"
    visitor_id = "v_ooo"

    t_mid = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)
    t_early = datetime(2026, 9, 8, 8, 0, 0, tzinfo=timezone.utc)
    t_late = datetime(2026, 9, 8, 18, 0, 0, tzinfo=timezone.utc)

    # Ingest t_mid first
    await visitor_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_mid)
    # Ingest t_late
    await visitor_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "g1", t_late)
    # Ingest t_early (out of order, earlier than first event)
    await visitor_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "g1", t_early)

    profile = await visitor_service.get_visitor_profile(venue_id, visitor_id)
    assert profile.first_seen == t_early.isoformat()
    assert profile.last_seen == t_late.isoformat()


@pytest.mark.asyncio
async def test_concurrent_event_ingestion(visitor_service):
    """Test concurrent ENTRY events for same visitor do not violate state integrity."""
    venue_id = "concur_venue"
    visitor_id = "v_concur"
    t_base = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)

    async def ingest_entry(i):
        t = t_base + timedelta(seconds=i)
        return await visitor_service.record_movement_event(
            venue_id=venue_id,
            session_id="s1",
            visitor_id=visitor_id,
            event_type="ENTRY",
            gate_id=f"gate_{i}",
            timestamp=t,
        )

    # Launch 5 concurrent ENTRY requests
    results = await asyncio.gather(*(ingest_entry(i) for i in range(5)))
    assert len(results) == 5

    profile = await visitor_service.get_visitor_profile(venue_id, visitor_id)
    assert profile.total_entries == 5
    # Since all entries were concurrent while visits were being opened/attached:
    # At most 1 OPEN visit is created because of the partial unique index!
    visits = await visitor_service.get_visitor_visits(venue_id, visitor_id)
    open_visits = [v for v in visits.visits if v.status == "OPEN"]
    assert len(open_visits) == 1


@pytest.mark.asyncio
async def test_pagination_and_date_boundaries(visitor_service):
    """Test pagination (limit, skip) and date range filtering."""
    venue_id = "page_venue"
    visitor_id = "v_page"

    # Ingest 10 events over 10 hours
    t_base = datetime(2026, 9, 8, 8, 0, 0, tzinfo=timezone.utc)
    for i in range(10):
        t = t_base + timedelta(hours=i)
        await visitor_service.record_movement_event(
            venue_id, "s1", visitor_id, "ENTRY" if i % 2 == 0 else "EXIT", f"g_{i}", t
        )

    # Test limit and skip
    page1 = await visitor_service.get_visitor_events(venue_id, visitor_id, limit=3, skip=0)
    assert len(page1.events) == 3
    assert page1.total == 10

    page2 = await visitor_service.get_visitor_events(venue_id, visitor_id, limit=3, skip=3)
    assert len(page2.events) == 3
    assert page2.events[0].gate_id != page1.events[0].gate_id

    # Test date boundary filter (hours 2 to 5)
    t_start = (t_base + timedelta(hours=2)).isoformat()
    t_end = (t_base + timedelta(hours=5)).isoformat()
    filtered = await visitor_service.get_visitor_events(
        venue_id, visitor_id, start_time=t_start, end_time=t_end, limit=20
    )
    assert filtered.total == 4


@pytest.mark.asyncio
async def test_degraded_mongodb_mode():
    """Test VisitorHistoryService gracefully returns when MongoDB collections are None."""
    svc = VisitorHistoryService(
        visitor_repo=VisitorRepository(None),
        event_repo=VisitorEventRepository(None),
        visit_repo=VisitRepository(None),
    )
    assert not svc.is_available

    # record_movement_event should not raise exception
    res = await svc.record_movement_event(
        venue_id="deg_v",
        session_id="deg_s",
        visitor_id="deg_vis",
        event_type="ENTRY",
        gate_id="g1",
    )
    assert res["status"] == "processed"

    # Profile lookup should raise NotFoundException gracefully
    with pytest.raises(NotFoundException):
        await svc.get_visitor_profile("deg_v", "deg_vis")


@pytest.mark.asyncio
async def test_repository_idempotent_index_creation(repo_test_db):
    """Test create_all_indexes idempotency on startup."""
    from app.database.mongodb.indexes import create_all_indexes
    res1 = await create_all_indexes(repo_test_db)
    assert "visitors" in res1
    assert "visitor_events" in res1
    assert "visits" in res1

    # Running a second time is completely safe and idempotent
    res2 = await create_all_indexes(repo_test_db)
    assert "visitors" in res2


@pytest.mark.asyncio
async def test_visitor_service_idempotency_different_uuid_same_source_event(visitor_service):
    """
    CTO Constraint 2 Test:
    Request A: source_event_id = event_123, visitor_event_id = UUID_A
    Request B: source_event_id = event_123, visitor_event_id = UUID_B
    Verify that Request B is suppressed, does NOT increment counters, and does NOT create duplicate visits.
    """
    venue_id = "idem_venue"
    visitor_id = "v_idem"
    t = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)

    # Request A
    res_a = await visitor_service.record_movement_event(
        venue_id=venue_id,
        session_id="s1",
        visitor_id=visitor_id,
        event_type="ENTRY",
        gate_id="gate_1",
        timestamp=t,
        source_event_id="event_123",
        visitor_event_id="UUID_A",
    )
    assert res_a["status"] == "processed"
    assert res_a["is_new_visit"] is True

    # Request B with SAME source_event_id but DIFFERENT visitor_event_id
    res_b = await visitor_service.record_movement_event(
        venue_id=venue_id,
        session_id="s1",
        visitor_id=visitor_id,
        event_type="ENTRY",
        gate_id="gate_1",
        timestamp=t,
        source_event_id="event_123",
        visitor_event_id="UUID_B",
    )
    assert res_b["status"] == "ignored"
    assert res_b["reason"] == "duplicate_source_event"

    # Profile check: counters must NOT be incremented twice!
    profile = await visitor_service.get_visitor_profile(venue_id, visitor_id)
    assert profile.total_entries == 1
    assert profile.total_visits == 1

    # Visits check: exactly 1 visit must exist
    visits = await visitor_service.get_visitor_visits(venue_id, visitor_id)
    assert visits.total == 1


@pytest.mark.asyncio
async def test_out_of_order_negative_duration_prevention(visitor_service):
    """
    CTO Constraint 4 Test:
    Verify an EXIT timestamp earlier than entry_time cannot produce a negative duration (deterministic 0.0).
    """
    venue_id = "neg_dur_venue"
    visitor_id = "v_neg"
    t_in = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)
    t_out_earlier = datetime(2026, 9, 8, 11, 30, 0, tzinfo=timezone.utc)  # earlier than entry

    await visitor_service.record_movement_event(venue_id, "s1", visitor_id, "ENTRY", "gate_1", t_in)
    await visitor_service.record_movement_event(venue_id, "s1", visitor_id, "EXIT", "gate_1", t_out_earlier)

    visits = await visitor_service.get_visitor_visits(venue_id, visitor_id)
    assert visits.total == 1
    assert visits.visits[0].status == "COMPLETED"
    assert visits.visits[0].duration_seconds == 0.0  # clamped to 0.0, never negative!

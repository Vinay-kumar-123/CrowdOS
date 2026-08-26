"""
Sprint 10 — Repository Layer Unit Tests.

Tests all repository classes: BaseRepository, VenueRepository, SessionRepository,
EventRepository, AlertRepository, PredictionRepository using isolated MongoMock collections.
"""
import pytest
from datetime import datetime, timezone
from mongomock_motor import AsyncMongoMockClient
from app.models.venue import VenueDBModel
from app.models.session import SessionDBModel
from app.models.event import EventDBModel
from app.models.alert import AlertDBModel
from app.models.prediction import PredictionDBModel
from app.repositories.base import BaseRepository
from app.repositories.venue_repository import VenueRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.event_repository import EventRepository
from app.repositories.alert_repository import AlertRepository
from app.repositories.prediction_repository import PredictionRepository


@pytest.fixture
def test_db():
    client = AsyncMongoMockClient()
    return client["test_repo_db"]


# ---------------------------------------------------------------------------
# BaseRepository Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_base_repository_crud(test_db):
    repo = BaseRepository(test_db["generic_coll"], VenueDBModel)
    assert repo.is_available

    # Create
    venue = VenueDBModel(venue_id="base_v1", name="Base Venue 1", capacity=500)
    created = await repo.create(venue)
    assert created.venue_id == "base_v1"

    # Count
    cnt = await repo.count()
    assert cnt == 1

    # Find one
    fetched = await repo.find_one({"venue_id": "base_v1"})
    assert fetched is not None
    assert fetched.name == "Base Venue 1"
    assert fetched.capacity == 500

    # Update
    updated = await repo.update_by_filter({"venue_id": "base_v1"}, {"name": "Updated Venue 1"})
    assert updated is True
    refetched = await repo.find_one({"venue_id": "base_v1"})
    assert refetched.name == "Updated Venue 1"

    # Find many
    all_venues = await repo.find_many()
    assert len(all_venues) == 1

    # Delete
    deleted = await repo.delete_one({"venue_id": "base_v1"})
    assert deleted is True
    assert await repo.count() == 0


@pytest.mark.asyncio
async def test_base_repository_unavailable():
    """Verify repository returns safe defaults when collection is None (degraded mode)."""
    repo = BaseRepository(None, VenueDBModel)
    assert not repo.is_available

    venue = VenueDBModel(venue_id="deg_v1", name="Degraded Venue")
    assert await repo.create(venue) == venue
    assert await repo.get_by_id("deg_v1") is None
    assert await repo.find_one({"venue_id": "deg_v1"}) is None
    assert await repo.find_many() == []
    assert await repo.update_by_filter({"venue_id": "deg_v1"}, {}) is False
    assert await repo.count() == 0
    assert await repo.delete_one({"venue_id": "deg_v1"}) is False


# ---------------------------------------------------------------------------
# VenueRepository Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_venue_repository(test_db):
    repo = VenueRepository(test_db["venues"])

    # Upsert
    venue = VenueDBModel(venue_id="ven_101", name="Grand Arena", capacity=25000)
    await repo.upsert_venue(venue)

    # Get
    v = await repo.get_by_venue_id("ven_101")
    assert v is not None
    assert v.venue_id == "ven_101"
    assert v.capacity == 25000

    # Upsert existing (update capacity)
    venue_updated = VenueDBModel(venue_id="ven_101", name="Grand Arena Extended", capacity=30000)
    await repo.upsert_venue(venue_updated)

    v_after = await repo.get_by_venue_id("ven_101")
    assert v_after.capacity == 30000
    assert v_after.name == "Grand Arena Extended"

    # List
    v_list = await repo.list_venues()
    assert len(v_list) == 1


# ---------------------------------------------------------------------------
# SessionRepository Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_repository(test_db):
    repo = SessionRepository(test_db["sessions"])

    sess = SessionDBModel(
        session_id="sess_101",
        venue_id="ven_101",
        status="CREATED",
        metadata={"operator": "john_doe"},
    )
    await repo.create(sess)

    # Fetch
    s = await repo.get_by_session_id("sess_101")
    assert s is not None
    assert s.status == "CREATED"

    # Update to ACTIVE
    now_iso = datetime.now(timezone.utc).isoformat()
    await repo.update_session_state("sess_101", "ACTIVE", {"started_at": now_iso})

    s_active = await repo.get_by_session_id("sess_101")
    assert s_active.status == "ACTIVE"
    assert s_active.started_at == now_iso

    # Get active session
    active = await repo.get_active_session("ven_101")
    assert active is not None
    assert active.session_id == "sess_101"

    # Save summary and stop
    summary_data = {"total_entries": 120, "total_exits": 40, "peak_occupancy": 85}
    await repo.save_session_summary("sess_101", summary_data, stopped_at=now_iso)

    s_stopped = await repo.get_by_session_id("sess_101")
    assert s_stopped.status == "STOPPED"
    assert s_stopped.summary == summary_data

    # List by venue
    s_list = await repo.list_by_venue("ven_101")
    assert len(s_list) == 1


# ---------------------------------------------------------------------------
# EventRepository Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_event_repository(test_db):
    repo = EventRepository(test_db["events"])

    ev = EventDBModel(
        event_id="ev_001",
        venue_id="ven_101",
        session_id="sess_101",
        event_type="ENTRY",
        gate_id="gate_north",
        timestamp=datetime.now(timezone.utc).isoformat(),
        status="processed",
    )
    await repo.save_event(ev)

    # Fetch
    fetched = await repo.get_by_event_id("ev_001")
    assert fetched is not None
    assert fetched.event_id == "ev_001"
    assert fetched.event_type == "ENTRY"
    assert fetched.gate_id == "gate_north"

    # Duplicate save is safe
    dup = await repo.save_event(ev)
    assert dup is not None

    # List by session
    session_events = await repo.list_events_by_session("sess_101")
    assert len(session_events) == 1

    # List by venue
    venue_events = await repo.list_events_by_venue("ven_101")
    assert len(venue_events) == 1


# ---------------------------------------------------------------------------
# AlertRepository Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_alert_repository(test_db):
    repo = AlertRepository(test_db["alerts"])

    alert = AlertDBModel(
        alert_id="alt_001",
        session_id="sess_101",
        venue_id="ven_101",
        gate_id="gate_north",
        type="SURGE",
        severity="HIGH",
        status="ACTIVE",
        created_at_iso=datetime.now(timezone.utc).isoformat(),
        last_seen_iso=datetime.now(timezone.utc).isoformat(),
    )
    await repo.save_or_update_alert(alert)

    # Fetch
    fetched = await repo.get_by_alert_id("alt_001")
    assert fetched is not None
    assert fetched.type == "SURGE"
    assert fetched.severity == "HIGH"

    # List active
    active = await repo.list_active_alerts("ven_101")
    assert len(active) == 1

    # Resolve alert
    alert.status = "RESOLVED"
    alert.resolved_at_iso = datetime.now(timezone.utc).isoformat()
    await repo.save_or_update_alert(alert)

    active_after = await repo.list_active_alerts("ven_101")
    assert len(active_after) == 0

    all_alerts = await repo.list_all_alerts("ven_101")
    assert len(all_alerts) == 1


# ---------------------------------------------------------------------------
# PredictionRepository Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prediction_repository(test_db):
    repo = PredictionRepository(test_db["predictions"])

    pred = PredictionDBModel(
        prediction_id="pred_001",
        session_id="sess_101",
        venue_id="ven_101",
        timestamp=datetime.now(timezone.utc).isoformat(),
        risk_score=68.5,
        risk_level="HIGH",
        trend_direction="INCREASING",
        primary_recommendation="REDUCE_GATE_INFLOW",
    )
    await repo.save_prediction(pred)

    # Fetch
    fetched = await repo.get_by_prediction_id("pred_001")
    assert fetched is not None
    assert fetched.risk_score == 68.5
    assert fetched.risk_level == "HIGH"
    assert fetched.primary_recommendation == "REDUCE_GATE_INFLOW"

    # List history
    history = await repo.list_predictions("ven_101", "sess_101")
    assert len(history) == 1

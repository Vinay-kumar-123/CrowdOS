"""
Tests for Session Management (Lifecycle, transitions, duplicate operations, expiration).
"""
import pytest
import time
from intelligence.session.session import MonitoringSession, SessionStatus
from intelligence.session.session_manager import SessionManager


def test_create_session():
    mgr = SessionManager(venue_id="venue_A")
    session = mgr.create_session()
    assert session.session_id is not None
    assert session.status == SessionStatus.CREATED
    assert session.venue_id == "venue_A"


def test_start_session():
    mgr = SessionManager()
    session = mgr.create_session()
    assert mgr.start_session(session.session_id)
    assert session.status == SessionStatus.ACTIVE
    assert session.started_at is not None


def test_pause_and_resume_session():
    mgr = SessionManager()
    session = mgr.create_session()
    mgr.start_session(session.session_id)

    # Pause
    assert mgr.pause_session(session.session_id)
    assert session.status == SessionStatus.PAUSED

    # Resume
    assert mgr.resume_session(session.session_id)
    assert session.status == SessionStatus.ACTIVE


def test_stop_session():
    mgr = SessionManager()
    session = mgr.create_session()
    mgr.start_session(session.session_id)

    assert mgr.stop_session(session.session_id)
    assert session.status == SessionStatus.STOPPED
    assert session.stopped_at is not None


def test_duplicate_start():
    """Duplicate start on ACTIVE session should return True idempotently without resetting timestamp."""
    mgr = SessionManager()
    session = mgr.create_session()
    mgr.start_session(session.session_id)
    ts1 = session.started_at

    # Second start
    assert mgr.start_session(session.session_id)
    assert session.status == SessionStatus.ACTIVE
    assert session.started_at == ts1


def test_duplicate_stop():
    """Duplicate stop on STOPPED session should return True idempotently."""
    mgr = SessionManager()
    session = mgr.create_session()
    mgr.start_session(session.session_id)
    mgr.stop_session(session.session_id)

    # Second stop
    assert mgr.stop_session(session.session_id)
    assert session.status == SessionStatus.STOPPED


def test_invalid_state_transition():
    """Direct transition from CREATED to STOPPED or PAUSED is invalid."""
    mgr = SessionManager()
    session = mgr.create_session()

    assert not mgr.pause_session(session.session_id)
    assert not mgr.stop_session(session.session_id)
    assert session.status == SessionStatus.CREATED


def test_session_expiration_check():
    """Deterministic expiration check marks active sessions exceeding max duration as EXPIRED."""
    mgr = SessionManager()
    session = mgr.create_session()
    session.max_duration_seconds = 10.0  # 10s max duration
    mgr.start_session(session.session_id)

    # Simulate 15s elapsed
    start_ts = time.time()
    expired_ids = mgr.check_expiration(now_epoch=start_ts + 15.0)

    assert session.session_id in expired_ids
    assert session.status == SessionStatus.EXPIRED

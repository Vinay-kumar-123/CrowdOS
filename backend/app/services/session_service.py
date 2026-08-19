"""
Session Service — Sprint 9.

Implements session lifecycle operations against Sprint 7's SessionManager
via the VenueEngineRegistry adapter.

Architecture constraints:
    - ALL AI Engine calls are synchronous.
    - NO persistence logic — Persistence is deferred to Sprint 10.
    - Business intelligence (risk, alerts, flow) belongs to AI Engine, not here.
"""
import logging
from typing import Dict, List, Optional, Any
from app.services.ai_engine_adapter import VenueEngineRegistry, VenueEngines
from app.schemas.session import (
    SessionCreateRequest,
    SessionStatusResponse,
    SessionListResponse,
    SessionActionResponse,
    SessionSummaryResponse,
)
from app.core.exceptions import NotFoundException, CrowdOSException

logger = logging.getLogger("crowdos.session_service")


class SessionService:
    """
    Thin service layer for session lifecycle.
    All calls delegate directly to Sprint 7's SessionManager.
    """

    def __init__(self, registry: VenueEngineRegistry):
        self._registry = registry

    def _get_engines(self, venue_id: str) -> VenueEngines:
        engines = self._registry.get(venue_id)
        if engines is None:
            raise NotFoundException(f"Venue '{venue_id}' not initialized. Create a session first.")
        return engines

    # ------------------------------------------------------------------
    # Create session
    # ------------------------------------------------------------------

    def create_session(
        self,
        venue_id: str,
        request: SessionCreateRequest,
    ) -> SessionStatusResponse:
        """
        Create a new monitoring session for a venue.
        Initializes VenueEngines on first call.
        """
        engines = self._registry.get_or_create(
            venue_id=venue_id,
            venue_capacity=request.venue_capacity,
        )

        session = engines.intelligence.session_manager.create_session(
            venue_id=venue_id,
            metadata=request.metadata,
        )

        logger.info(f"Session created: {session.session_id} for venue: {venue_id}")

        return SessionStatusResponse(
            session_id=session.session_id,
            venue_id=session.venue_id,
            status=_status_str(session),
            started_at=session.started_at,
            stopped_at=session.stopped_at,
            metadata=session.metadata,
        )

    # ------------------------------------------------------------------
    # Get session
    # ------------------------------------------------------------------

    def get_session(self, venue_id: str, session_id: str) -> SessionStatusResponse:
        engines = self._get_engines(venue_id)
        session = engines.intelligence.session_manager.get_session(session_id)
        if session is None:
            raise NotFoundException(f"Session '{session_id}' not found for venue '{venue_id}'.")
        return SessionStatusResponse(
            session_id=session.session_id,
            venue_id=session.venue_id,
            status=_status_str(session),
            started_at=session.started_at,
            stopped_at=session.stopped_at,
            metadata=session.metadata,
        )

    # ------------------------------------------------------------------
    # List sessions
    # ------------------------------------------------------------------

    def list_sessions(self, venue_id: str) -> SessionListResponse:
        engines = self._get_engines(venue_id)
        sessions = engines.intelligence.session_manager.list_sessions()
        items = [
            SessionStatusResponse(
                session_id=s.session_id,
                venue_id=s.venue_id,
                status=_status_str(s),
                started_at=s.started_at,
                stopped_at=s.stopped_at,
                metadata=s.metadata,
            )
            for s in sessions
        ]
        return SessionListResponse(
            venue_id=venue_id,
            sessions=items,
            total=len(items),
        )

    # ------------------------------------------------------------------
    # Start session
    # ------------------------------------------------------------------

    def start_session(self, venue_id: str, session_id: str) -> SessionActionResponse:
        engines = self._get_engines(venue_id)
        session = engines.intelligence.session_manager.get_session(session_id)
        if session is None:
            raise NotFoundException(f"Session '{session_id}' not found for venue '{venue_id}'.")

        success = engines.intelligence.session_manager.start_session(session_id)
        if not success:
            raise CrowdOSException(
                detail=f"Cannot start session '{session_id}' from state '{_status_str(session)}'.",
                status_code=409,
            )

        # Refresh
        session = engines.intelligence.session_manager.get_session(session_id)
        return SessionActionResponse(
            session_id=session_id,
            venue_id=venue_id,
            action="start",
            success=True,
            status=_status_str(session),
            message=f"Session '{session_id}' started.",
        )

    # ------------------------------------------------------------------
    # Pause session
    # ------------------------------------------------------------------

    def pause_session(self, venue_id: str, session_id: str) -> SessionActionResponse:
        engines = self._get_engines(venue_id)
        session = engines.intelligence.session_manager.get_session(session_id)
        if session is None:
            raise NotFoundException(f"Session '{session_id}' not found.")

        success = engines.intelligence.session_manager.pause_session(session_id)
        if not success:
            raise CrowdOSException(
                detail=f"Cannot pause session '{session_id}' from state '{_status_str(session)}'.",
                status_code=409,
            )
        session = engines.intelligence.session_manager.get_session(session_id)
        return SessionActionResponse(
            session_id=session_id, venue_id=venue_id, action="pause",
            success=True, status=_status_str(session), message=f"Session '{session_id}' paused.",
        )

    # ------------------------------------------------------------------
    # Resume session
    # ------------------------------------------------------------------

    def resume_session(self, venue_id: str, session_id: str) -> SessionActionResponse:
        engines = self._get_engines(venue_id)
        session = engines.intelligence.session_manager.get_session(session_id)
        if session is None:
            raise NotFoundException(f"Session '{session_id}' not found.")

        success = engines.intelligence.session_manager.resume_session(session_id)
        if not success:
            raise CrowdOSException(
                detail=f"Cannot resume session '{session_id}' from state '{_status_str(session)}'.",
                status_code=409,
            )
        session = engines.intelligence.session_manager.get_session(session_id)
        return SessionActionResponse(
            session_id=session_id, venue_id=venue_id, action="resume",
            success=True, status=_status_str(session), message=f"Session '{session_id}' resumed.",
        )

    # ------------------------------------------------------------------
    # Stop session
    # ------------------------------------------------------------------

    def stop_session(self, venue_id: str, session_id: str) -> SessionSummaryResponse:
        """Stop session and return immutable summary from Sprint 7."""
        engines = self._get_engines(venue_id)
        session = engines.intelligence.session_manager.get_session(session_id)
        if session is None:
            raise NotFoundException(f"Session '{session_id}' not found.")

        summary = engines.intelligence.stop_session(session_id)

        if summary is None:
            # Already stopped — try to retrieve existing status
            return SessionSummaryResponse(
                session_id=session_id,
                venue_id=venue_id,
                started_at=getattr(session, "started_at", None),
                stopped_at=getattr(session, "stopped_at", None),
            )

        s = summary if isinstance(summary, dict) else summary.to_dict()
        return SessionSummaryResponse(**s)

    # ------------------------------------------------------------------
    # Check expiration
    # ------------------------------------------------------------------

    def check_expirations(self, venue_id: str, now_epoch: Optional[float] = None) -> List[str]:
        """Trigger deterministic expiration check in Sprint 7 SessionManager."""
        engines = self._get_engines(venue_id)
        return engines.intelligence.session_manager.check_expiration(now_epoch=now_epoch)

    # ------------------------------------------------------------------
    # Active session
    # ------------------------------------------------------------------

    def get_active_session(self, venue_id: str) -> Optional[SessionStatusResponse]:
        engines = self._get_engines(venue_id)
        session = engines.intelligence.session_manager.get_active_session()
        if session is None:
            return None
        return SessionStatusResponse(
            session_id=session.session_id,
            venue_id=session.venue_id,
            status=_status_str(session),
            started_at=session.started_at,
            stopped_at=session.stopped_at,
            metadata=session.metadata,
        )


def _status_str(session) -> str:
    """Extract status string from a session object regardless of how status is stored."""
    st = getattr(session, "status", None)
    if st is None:
        return "UNKNOWN"
    if hasattr(st, "value"):
        return st.value
    return str(st)

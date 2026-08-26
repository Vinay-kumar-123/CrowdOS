"""
Session Service — Sprint 10.

Implements session lifecycle operations against Sprint 7's SessionManager
via the VenueEngineRegistry adapter and persists session lifecycle to MongoDB.

Architecture:
    FastAPI Endpoints → SessionService → Sprint 7 SessionManager (Live State Machine)
                                       → SessionRepository (MongoDB Persistence)

Constraints:
    - Sprint 7 SessionManager remains the single source of truth for in-flight state transitions.
    - MongoDB stores persistent session records, status changes, and final session summaries.
    - If MongoDB is down, service gracefully logs error and continues with in-memory execution.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from app.services.ai_engine_adapter import VenueEngineRegistry, VenueEngines
from app.repositories.session_repository import SessionRepository
from app.repositories.venue_repository import VenueRepository
from app.models.session import SessionDBModel
from app.models.venue import VenueDBModel
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
    Service layer for session lifecycle coordinating live AI Engine state and MongoDB persistence.
    """

    def __init__(
        self,
        registry: VenueEngineRegistry,
        session_repo: Optional[SessionRepository] = None,
        venue_repo: Optional[VenueRepository] = None,
    ):
        self._registry = registry
        self._session_repo = session_repo
        self._venue_repo = venue_repo

    async def _ensure_venue_exists(self, venue_id: str) -> Optional[VenueEngines]:
        engines = self._registry.get(venue_id)
        if engines is not None:
            return engines

        if self._venue_repo and self._venue_repo.is_available:
            v = await self._venue_repo.get_by_venue_id(venue_id)
            if v is not None:
                return None

        raise NotFoundException(f"Venue '{venue_id}' not initialized. Create a session first.")

    def _get_engines(self, venue_id: str) -> VenueEngines:
        engines = self._registry.get(venue_id)
        if engines is None:
            raise NotFoundException(f"Venue '{venue_id}' not initialized. Create a session first.")
        return engines

    # ------------------------------------------------------------------
    # Create session
    # ------------------------------------------------------------------

    async def create_session(
        self,
        venue_id: str,
        request: SessionCreateRequest,
    ) -> SessionStatusResponse:
        """
        Create a new monitoring session for a venue.
        Initializes in-memory VenueEngines and persists session record to MongoDB.
        """
        engines = self._registry.get_or_create(
            venue_id=venue_id,
            venue_capacity=request.venue_capacity,
        )

        session = engines.intelligence.session_manager.create_session(
            venue_id=venue_id,
            metadata=request.metadata,
        )

        status_str = _status_str(session)
        logger.info(f"Session created: {session.session_id} for venue: {venue_id}")

        # Persist session to MongoDB
        if self._session_repo and self._session_repo.is_available:
            session_model = SessionDBModel(
                session_id=session.session_id,
                venue_id=session.venue_id,
                status=status_str,
                started_at=session.started_at,
                stopped_at=session.stopped_at,
                metadata=session.metadata or {},
            )
            await self._session_repo.create(session_model)

        # Persist venue metadata
        if self._venue_repo and self._venue_repo.is_available:
            venue_model = VenueDBModel(
                venue_id=venue_id,
                name=f"Venue {venue_id}",
                capacity=request.venue_capacity,
            )
            await self._venue_repo.upsert_venue(venue_model)

        # Real-time session broadcast (Sprint 11)
        try:
            from app.realtime.broadcaster import broadcaster
            await broadcaster.broadcast_session_update(
                venue_id=venue_id,
                session_id=session.session_id,
                status=status_str,
                action="create",
                started_at=session.started_at,
                stopped_at=session.stopped_at,
                message=f"Session '{session.session_id}' created for venue '{venue_id}'.",
            )
        except Exception as be:
            logger.warning(f"Real-time session broadcast notice: {be}")

        return SessionStatusResponse(
            session_id=session.session_id,
            venue_id=session.venue_id,
            status=status_str,
            started_at=session.started_at,
            stopped_at=session.stopped_at,
            metadata=session.metadata,
        )

    # ------------------------------------------------------------------
    # Get session
    # ------------------------------------------------------------------

    async def get_session(self, venue_id: str, session_id: str) -> SessionStatusResponse:
        # First check in-memory engine
        engines = self._registry.get(venue_id)
        if engines is not None:
            session = engines.intelligence.session_manager.get_session(session_id)
            if session is not None:
                return SessionStatusResponse(
                    session_id=session.session_id,
                    venue_id=session.venue_id,
                    status=_status_str(session),
                    started_at=session.started_at,
                    stopped_at=session.stopped_at,
                    metadata=session.metadata,
                )

        # Fallback to MongoDB persistence
        if self._session_repo and self._session_repo.is_available:
            persisted = await self._session_repo.get_by_session_id(session_id)
            if persisted and persisted.venue_id == venue_id:
                return SessionStatusResponse(
                    session_id=persisted.session_id,
                    venue_id=persisted.venue_id,
                    status=persisted.status,
                    started_at=persisted.started_at,
                    stopped_at=persisted.stopped_at,
                    metadata=persisted.metadata,
                )

        raise NotFoundException(f"Session '{session_id}' not found for venue '{venue_id}'.")

    # ------------------------------------------------------------------
    # List sessions
    # ------------------------------------------------------------------

    async def list_sessions(self, venue_id: str) -> SessionListResponse:
        engines = self._registry.get(venue_id)
        has_persisted_venue = False
        persisted_sessions = []

        if self._venue_repo and self._venue_repo.is_available:
            v = await self._venue_repo.get_by_venue_id(venue_id)
            if v is not None:
                has_persisted_venue = True

        if self._session_repo and self._session_repo.is_available:
            persisted_sessions = await self._session_repo.list_by_venue(venue_id)

        if engines is None and not has_persisted_venue and not persisted_sessions:
            raise NotFoundException(f"Venue '{venue_id}' not initialized. Create a session first.")

        session_map: Dict[str, SessionStatusResponse] = {}

        # Query in-memory session manager
        if engines is not None:
            sessions = engines.intelligence.session_manager.list_sessions()
            for s in sessions:
                session_map[s.session_id] = SessionStatusResponse(
                    session_id=s.session_id,
                    venue_id=s.venue_id,
                    status=_status_str(s),
                    started_at=s.started_at,
                    stopped_at=s.stopped_at,
                    metadata=s.metadata,
                )

        # Query MongoDB
        for p in persisted_sessions:
            if p.session_id not in session_map:
                session_map[p.session_id] = SessionStatusResponse(
                    session_id=p.session_id,
                    venue_id=p.venue_id,
                    status=p.status,
                    started_at=p.started_at,
                    stopped_at=p.stopped_at,
                    metadata=p.metadata,
                )

        items = list(session_map.values())
        return SessionListResponse(
            venue_id=venue_id,
            sessions=items,
            total=len(items),
        )

    # ------------------------------------------------------------------
    # Start session
    # ------------------------------------------------------------------

    async def start_session(self, venue_id: str, session_id: str) -> SessionActionResponse:
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

        # Refresh in-memory state
        session = engines.intelligence.session_manager.get_session(session_id)
        status_str = _status_str(session)

        # Update MongoDB
        if self._session_repo and self._session_repo.is_available:
            await self._session_repo.update_session_state(
                session_id=session_id,
                status=status_str,
                additional_fields={"started_at": session.started_at},
            )

        # Real-time session broadcast (Sprint 11)
        try:
            from app.realtime.broadcaster import broadcaster
            await broadcaster.broadcast_session_update(
                venue_id=venue_id,
                session_id=session_id,
                status=status_str,
                action="start",
                started_at=session.started_at,
                message=f"Session '{session_id}' started.",
            )
        except Exception as be:
            logger.warning(f"Real-time session broadcast notice: {be}")

        return SessionActionResponse(
            session_id=session_id,
            venue_id=venue_id,
            action="start",
            success=True,
            status=status_str,
            message=f"Session '{session_id}' started.",
        )

    # ------------------------------------------------------------------
    # Pause session
    # ------------------------------------------------------------------

    async def pause_session(self, venue_id: str, session_id: str) -> SessionActionResponse:
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
        status_str = _status_str(session)
        pause_time = datetime.now(timezone.utc).isoformat()

        # Update MongoDB
        if self._session_repo and self._session_repo.is_available:
            await self._session_repo.update_session_state(
                session_id=session_id,
                status=status_str,
                additional_fields={"paused_at": pause_time},
            )

        # Real-time session broadcast (Sprint 11)
        try:
            from app.realtime.broadcaster import broadcaster
            await broadcaster.broadcast_session_update(
                venue_id=venue_id,
                session_id=session_id,
                status=status_str,
                action="pause",
                paused_at=pause_time,
                message=f"Session '{session_id}' paused.",
            )
        except Exception as be:
            logger.warning(f"Real-time session broadcast notice: {be}")

        return SessionActionResponse(
            session_id=session_id,
            venue_id=venue_id,
            action="pause",
            success=True,
            status=status_str,
            message=f"Session '{session_id}' paused.",
        )

    # ------------------------------------------------------------------
    # Resume session
    # ------------------------------------------------------------------

    async def resume_session(self, venue_id: str, session_id: str) -> SessionActionResponse:
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
        status_str = _status_str(session)
        resume_time = datetime.now(timezone.utc).isoformat()

        # Update MongoDB
        if self._session_repo and self._session_repo.is_available:
            await self._session_repo.update_session_state(
                session_id=session_id,
                status=status_str,
                additional_fields={"resumed_at": resume_time},
            )

        # Real-time session broadcast (Sprint 11)
        try:
            from app.realtime.broadcaster import broadcaster
            await broadcaster.broadcast_session_update(
                venue_id=venue_id,
                session_id=session_id,
                status=status_str,
                action="resume",
                resumed_at=resume_time,
                message=f"Session '{session_id}' resumed.",
            )
        except Exception as be:
            logger.warning(f"Real-time session broadcast notice: {be}")

        return SessionActionResponse(
            session_id=session_id,
            venue_id=venue_id,
            action="resume",
            success=True,
            status=status_str,
            message=f"Session '{session_id}' resumed.",
        )

    # ------------------------------------------------------------------
    # Stop session
    # ------------------------------------------------------------------

    async def stop_session(self, venue_id: str, session_id: str) -> SessionSummaryResponse:
        """Stop session and return immutable summary from Sprint 7, saving to MongoDB."""
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
        stopped_at = s.get("stopped_at") or datetime.now(timezone.utc).isoformat()

        # Persist summary to MongoDB
        if self._session_repo and self._session_repo.is_available:
            await self._session_repo.save_session_summary(
                session_id=session_id,
                summary=s,
                stopped_at=stopped_at,
            )

        # Real-time session broadcast (Sprint 11)
        try:
            from app.realtime.broadcaster import broadcaster
            await broadcaster.broadcast_session_update(
                venue_id=venue_id,
                session_id=session_id,
                status="STOPPED",
                action="stop",
                stopped_at=stopped_at,
                message=f"Session '{session_id}' stopped.",
                summary=s,
            )
        except Exception as be:
            logger.warning(f"Real-time session broadcast notice: {be}")

        return SessionSummaryResponse(**s)

    # ------------------------------------------------------------------
    # Check expiration
    # ------------------------------------------------------------------

    async def check_expirations(self, venue_id: str, now_epoch: Optional[float] = None) -> List[str]:
        """Trigger deterministic expiration check in Sprint 7 SessionManager and sync with MongoDB."""
        engines = self._get_engines(venue_id)
        expired_ids = engines.intelligence.session_manager.check_expiration(now_epoch=now_epoch)

        if expired_ids and self._session_repo and self._session_repo.is_available:
            now_iso = datetime.now(timezone.utc).isoformat()
            for sid in expired_ids:
                await self._session_repo.update_session_state(
                    session_id=sid,
                    status="EXPIRED",
                    additional_fields={"expired_at": now_iso},
                )

        if expired_ids:
            try:
                from app.realtime.broadcaster import broadcaster
                for sid in expired_ids:
                    await broadcaster.broadcast_session_update(
                        venue_id=venue_id,
                        session_id=sid,
                        status="EXPIRED",
                        action="expire",
                        message=f"Session '{sid}' expired.",
                    )
            except Exception as be:
                logger.warning(f"Real-time session expiration broadcast notice: {be}")

        return expired_ids

    # ------------------------------------------------------------------
    # Active session
    # ------------------------------------------------------------------

    async def get_active_session(self, venue_id: str) -> Optional[SessionStatusResponse]:
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

"""
Thread-safe Session Manager.
Manages session creation, start, pause, resume, stop, and deterministic expiration checks.
Enforces zero database persistence and thread safety via mutex locking.
"""
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional
from intelligence.session.session import MonitoringSession, SessionStatus
from intelligence.utils.logger import intelligence_logger


class SessionManager:
    """
    Thread-safe Monitoring Session Lifecycle Manager.
    """

    def __init__(self, venue_id: str = "default_venue"):
        self.venue_id = venue_id
        self._sessions: Dict[str, MonitoringSession] = {}
        self._active_session_id: Optional[str] = None
        self._lock = threading.Lock()

    def create_session(
        self,
        venue_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> MonitoringSession:
        target_venue = venue_id or self.venue_id
        session = MonitoringSession(
            session_id=session_id or None if session_id else MonitoringSession().session_id,
            venue_id=target_venue,
            metadata=metadata or {}
        )
        with self._lock:
            self._sessions[session.session_id] = session

        intelligence_logger.info(
            f"Created session {session.session_id} for venue {target_venue}",
            extra={"session_id": session.session_id, "venue_id": target_venue}
        )
        return session

    def start_session(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False

            # Duplicate start check
            if session.status == SessionStatus.ACTIVE:
                intelligence_logger.info(f"Session {session_id} already ACTIVE.")
                return True

            if not session.transition_to(SessionStatus.ACTIVE):
                intelligence_logger.warning(
                    f"Invalid state transition to ACTIVE for session {session_id} from {session.status}"
                )
                return False

            self._active_session_id = session_id

        intelligence_logger.info(f"Started session {session_id}")
        return True

    def pause_session(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or not session.transition_to(SessionStatus.PAUSED):
                return False
        intelligence_logger.info(f"Paused session {session_id}")
        return True

    def resume_session(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or not session.transition_to(SessionStatus.ACTIVE):
                return False
            self._active_session_id = session_id
        intelligence_logger.info(f"Resumed session {session_id}")
        return True

    def stop_session(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False

            # Idempotent stop check
            if session.status == SessionStatus.STOPPED:
                return True

            if not session.transition_to(SessionStatus.STOPPED):
                return False

            if self._active_session_id == session_id:
                self._active_session_id = None

        intelligence_logger.info(f"Stopped session {session_id}")
        return True

    def check_expiration(self, now_epoch: Optional[float] = None) -> List[str]:
        """
        Deterministic expiration check evaluating active sessions against max_duration_seconds.
        Documented Expiration Trigger: Session exceeds max_duration_seconds from started_at.
        Returns list of newly expired session IDs.
        """
        expired_ids = []
        now_ts = now_epoch if now_epoch is not None else datetime.now(timezone.utc).timestamp()

        with self._lock:
            for s_id, session in self._sessions.items():
                if session.status in (SessionStatus.ACTIVE, SessionStatus.PAUSED) and session.started_at:
                    try:
                        start_ts = datetime.fromisoformat(session.started_at.replace("Z", "+00:00")).timestamp()
                        if (now_ts - start_ts) >= session.max_duration_seconds:
                            if session.transition_to(SessionStatus.EXPIRED):
                                expired_ids.append(s_id)
                                if self._active_session_id == s_id:
                                    self._active_session_id = None
                    except Exception:
                        pass

        for s_id in expired_ids:
            intelligence_logger.info(f"Session {s_id} EXPIRED due to max duration threshold.")
        return expired_ids

    def get_session(self, session_id: str) -> Optional[MonitoringSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def get_active_session(self) -> Optional[MonitoringSession]:
        with self._lock:
            if self._active_session_id:
                return self._sessions.get(self._active_session_id)
            return None

    def list_sessions(self) -> List[MonitoringSession]:
        with self._lock:
            return list(self._sessions.values())

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._active_session_id = None

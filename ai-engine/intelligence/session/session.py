"""
Monitoring Session entity and explicit status lifecycle model.
"""
import uuid
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    EXPIRED = "EXPIRED"


class MonitoringSession(BaseModel):
    """
    In-memory continuous CrowdOS monitoring session.
    """
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    venue_id: str = Field(default="default_venue", description="Target venue ID")
    started_at: Optional[str] = Field(default=None)
    stopped_at: Optional[str] = Field(default=None)
    status: SessionStatus = Field(default=SessionStatus.CREATED)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    max_duration_seconds: float = Field(default=86400.0, description="Expiration threshold in seconds")

    def transition_to(self, target_status: SessionStatus) -> bool:
        """
        Validate and execute explicit state transition.
        Returns True if transition succeeded, False if invalid.
        """
        valid_transitions = {
            SessionStatus.CREATED: {SessionStatus.ACTIVE},
            SessionStatus.ACTIVE: {SessionStatus.PAUSED, SessionStatus.STOPPED, SessionStatus.EXPIRED},
            SessionStatus.PAUSED: {SessionStatus.ACTIVE, SessionStatus.STOPPED, SessionStatus.EXPIRED},
            SessionStatus.STOPPED: set(),  # Terminal state
            SessionStatus.EXPIRED: set(),  # Terminal state
        }

        allowed = valid_transitions.get(self.status, set())
        if target_status not in allowed:
            return False

        self.status = target_status
        now_iso = datetime.now(timezone.utc).isoformat()
        if target_status == SessionStatus.ACTIVE and not self.started_at:
            self.started_at = now_iso
        elif target_status in (SessionStatus.STOPPED, SessionStatus.EXPIRED):
            self.stopped_at = now_iso

        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "venue_id": self.venue_id,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "status": self.status.value if isinstance(self.status, SessionStatus) else str(self.status),
            "metadata": self.metadata,
        }

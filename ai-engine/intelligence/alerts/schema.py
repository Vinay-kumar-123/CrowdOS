"""
Data Models for Alert Engine.
Zero biometric vector or raw embedding fields.
"""
import uuid
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class AlertSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"


class AlertEvent(BaseModel):
    """
    In-memory Alert Event Payload.
    """
    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = Field(default="global_session")
    venue_id: str = Field(default="default_venue")
    gate_id: Optional[str] = Field(default=None, description="Specific gate ID or None for venue-level")
    type: str = Field(..., description="Anomaly or alert type string")
    severity: AlertSeverity = Field(default=AlertSeverity.MEDIUM)
    status: AlertStatus = Field(default=AlertStatus.ACTIVE)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_seen: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def mark_resolved(self, resolved_timestamp: Optional[str] = None) -> None:
        self.status = AlertStatus.RESOLVED
        self.resolved_at = resolved_timestamp or datetime.now(timezone.utc).isoformat()

    def update_last_seen(self, timestamp: Optional[str] = None) -> None:
        self.last_seen = timestamp or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "session_id": self.session_id,
            "venue_id": self.venue_id,
            "gate_id": self.gate_id,
            "type": self.type,
            "severity": self.severity.value if isinstance(self.severity, AlertSeverity) else str(self.severity),
            "status": self.status.value if isinstance(self.status, AlertStatus) else str(self.status),
            "created_at": self.created_at,
            "last_seen": self.last_seen,
            "resolved_at": self.resolved_at,
            "metadata": self.metadata,
        }

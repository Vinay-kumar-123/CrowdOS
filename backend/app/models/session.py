"""
Session Database Model — Sprint 10.
"""
from typing import Optional, Dict, Any
from pydantic import Field
from app.models.base import BaseDBModel


class SessionDBModel(BaseDBModel):
    """
    MongoDB document model for continuous monitoring sessions.
    Follows Sprint 7 SessionManager lifecycle semantics.
    """
    session_id: str = Field(..., description="Unique session identifier")
    venue_id: str = Field(..., description="Associated venue identifier")
    status: str = Field(default="CREATED", description="Session state: CREATED, ACTIVE, PAUSED, STOPPED, EXPIRED")
    started_at: Optional[str] = Field(default=None, description="ISO timestamp when session transitioned to ACTIVE")
    paused_at: Optional[str] = Field(default=None, description="ISO timestamp of most recent pause")
    resumed_at: Optional[str] = Field(default=None, description="ISO timestamp of most recent resume")
    stopped_at: Optional[str] = Field(default=None, description="ISO timestamp when session transitioned to STOPPED")
    expired_at: Optional[str] = Field(default=None, description="ISO timestamp if session expired")
    max_duration_seconds: float = Field(default=86400.0, description="Max allowed duration before auto-expiration")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom session metadata")
    summary: Optional[Dict[str, Any]] = Field(default=None, description="Sprint 7 SessionSummary generated upon stop")

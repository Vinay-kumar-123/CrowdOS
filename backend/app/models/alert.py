"""
Alert Database Model — Sprint 10.
"""
from typing import Optional
from pydantic import Field
from app.models.base import BaseDBModel


class AlertDBModel(BaseDBModel):
    """
    MongoDB document model for operational crowd intelligence alerts & anomalies.
    """
    alert_id: str = Field(..., description="Unique alert identifier")
    session_id: str = Field(..., description="Associated session identifier")
    venue_id: str = Field(..., description="Associated venue identifier")
    gate_id: Optional[str] = Field(default=None, description="Specific gate if applicable")
    type: str = Field(..., description="Alert anomaly type (e.g. SURGE, CAPACITY_EXCEEDED, GATE_IMBALANCE)")
    severity: str = Field(default="MEDIUM", description="INFO, LOW, MEDIUM, HIGH, CRITICAL")
    status: str = Field(default="ACTIVE", description="ACTIVE or RESOLVED")
    message: Optional[str] = Field(default=None, description="Human-readable alert description")
    created_at_iso: str = Field(default="", description="ISO timestamp when alert was first triggered")
    last_seen_iso: str = Field(default="", description="ISO timestamp when alert condition was last detected")
    resolved_at_iso: Optional[str] = Field(default=None, description="ISO timestamp when alert condition cleared")

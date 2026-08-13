"""
Global Settings for CrowdOS Event Intelligence Engine.
"""
from typing import List
from pydantic import BaseModel, Field


class IntelligenceSettings(BaseModel):
    """
    Configuration settings for historical time windows and memory capacity.
    """
    # Supported sliding windows in seconds: 1m, 5m, 15m, 60m
    supported_window_seconds: List[int] = Field(
        default=[60, 300, 900, 3600],
        description="Sliding window intervals in seconds"
    )
    max_window_capacity: int = Field(
        default=50000,
        description="Maximum items retained in any single sliding window buffer"
    )
    deduplication_window_seconds: float = Field(
        default=300.0,
        description="Sliding window for alert deduplication (5 minutes default)"
    )
    session_expiration_seconds: float = Field(
        default=86400.0,
        description="Default max active session duration (24 hours)"
    )


default_intelligence_settings = IntelligenceSettings()

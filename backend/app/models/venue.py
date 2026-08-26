"""
Venue Database Model — Sprint 10.
"""
from typing import Optional, Dict, Any
from pydantic import Field
from app.models.base import BaseDBModel


class VenueDBModel(BaseDBModel):
    """
    MongoDB document model for Venues.
    """
    venue_id: str = Field(..., description="Unique alphanumeric venue identifier")
    name: str = Field(default="", description="Human-readable venue name")
    capacity: int = Field(default=1000, ge=0, description="Configured venue capacity")
    description: Optional[str] = Field(default=None, description="Optional venue description")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom venue metadata")
    is_active: bool = Field(default=True, description="Whether the venue is active")

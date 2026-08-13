# Shared Events Data Contracts
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class BaseEvent(BaseModel):
    event_id: str
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    camera_id: str
    location_id: str

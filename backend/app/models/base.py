from datetime import datetime
from pydantic import BaseModel, Field


class BaseDBModel(BaseModel):
    """
    Base model for database entities.
    """
    id: str = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}

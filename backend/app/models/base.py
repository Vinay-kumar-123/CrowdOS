"""
Base Database Model — Sprint 10.

Base model for all MongoDB documents using Pydantic v2.
"""
from datetime import datetime, timezone
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BaseDBModel(BaseModel):
    """
    Base model for MongoDB database entities with common timestamp and serialization fields.
    """
    id: Optional[Any] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        arbitrary_types_allowed=True,
    )

    def to_mongo(self) -> Dict[str, Any]:
        """Convert model to dict suitable for MongoDB storage."""
        data = self.model_dump(by_alias=True, exclude_none=True)
        if "_id" in data and data["_id"] is None:
            del data["_id"]
        return data

    @classmethod
    def from_mongo(cls, doc: Dict[str, Any]):
        """Instantiate model from MongoDB document."""
        if not doc:
            return None
        doc_copy = dict(doc)
        if "_id" in doc_copy:
            doc_copy["_id"] = str(doc_copy["_id"])
            doc_copy["id"] = doc_copy["_id"]
        return cls(**doc_copy)

"""
Generic Base MongoDB Repository — Sprint 10.

Provides standard asynchronous CRUD data access methods over Motor collections.
Handles database availability checks gracefully so callers can operate in degraded mode.
"""
import logging
from typing import Generic, TypeVar, Optional, List, Type, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel

logger = logging.getLogger("crowdos.repositories.base")

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    """
    Abstract Generic Repository pattern implementing asynchronous MongoDB CRUD.
    """

    def __init__(self, collection, model_cls: Type[T]):
        self.collection = collection
        self.model_cls = model_cls

    @property
    def is_available(self) -> bool:
        return self.collection is not None

    async def create(self, entity: T) -> Optional[T]:
        """Insert a new document into the collection."""
        if not self.is_available:
            logger.debug(f"{self.model_cls.__name__} repository: database unavailable, skipping create.")
            return entity

        try:
            doc = entity.model_dump(by_alias=True, exclude_none=True)
            if "_id" in doc and doc["_id"] is None:
                del doc["_id"]
            await self.collection.insert_one(doc)
            return entity
        except Exception as e:
            logger.error(f"Error creating {self.model_cls.__name__} document: {e}")
            return entity

    async def get_by_id(self, id: str) -> Optional[T]:
        """Fetch a document by its '_id' or 'id'."""
        if not self.is_available:
            return None

        try:
            doc = await self.collection.find_one({"_id": id})
            if not doc:
                doc = await self.collection.find_one({"id": id})
            if doc:
                return self._to_model(doc)
            return None
        except Exception as e:
            logger.error(f"Error fetching {self.model_cls.__name__} by id '{id}': {e}")
            return None

    async def find_one(self, filter_query: Dict[str, Any]) -> Optional[T]:
        """Find a single document matching the filter query."""
        if not self.is_available:
            return None

        try:
            doc = await self.collection.find_one(filter_query)
            if doc:
                return self._to_model(doc)
            return None
        except Exception as e:
            logger.error(f"Error finding {self.model_cls.__name__} with filter {filter_query}: {e}")
            return None

    async def find_many(
        self,
        filter_query: Optional[Dict[str, Any]] = None,
        sort: Optional[List[tuple]] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[T]:
        """Find multiple documents matching the filter query with pagination and sorting."""
        if not self.is_available:
            return []

        try:
            query = filter_query or {}
            cursor = self.collection.find(query)
            if sort:
                cursor = cursor.sort(sort)
            if skip > 0:
                cursor = cursor.skip(skip)
            if limit > 0:
                cursor = cursor.limit(limit)

            docs = await cursor.to_list(length=limit)
            return [self._to_model(d) for d in docs if d]
        except Exception as e:
            logger.error(f"Error finding many {self.model_cls.__name__}: {e}")
            return []

    async def update_by_filter(
        self,
        filter_query: Dict[str, Any],
        update_data: Dict[str, Any],
        upsert: bool = False,
    ) -> bool:
        """Update documents matching filter_query with update_data."""
        if not self.is_available:
            return False

        try:
            update_payload = dict(update_data)
            update_payload["updated_at"] = datetime.now(timezone.utc)
            result = await self.collection.update_one(
                filter_query,
                {"$set": update_payload},
                upsert=upsert,
            )
            return result.acknowledged
        except Exception as e:
            logger.error(f"Error updating {self.model_cls.__name__}: {e}")
            return False

    async def count(self, filter_query: Optional[Dict[str, Any]] = None) -> int:
        """Count documents matching filter_query."""
        if not self.is_available:
            return 0

        try:
            query = filter_query or {}
            return await self.collection.count_documents(query)
        except Exception as e:
            logger.error(f"Error counting {self.model_cls.__name__}: {e}")
            return 0

    async def delete_one(self, filter_query: Dict[str, Any]) -> bool:
        """Delete a single document matching filter_query."""
        if not self.is_available:
            return False

        try:
            result = await self.collection.delete_one(filter_query)
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting {self.model_cls.__name__}: {e}")
            return False

    def _to_model(self, doc: Dict[str, Any]) -> T:
        """Convert a raw MongoDB document into a typed Pydantic model."""
        if not doc:
            return None
        doc_copy = dict(doc)
        if "_id" in doc_copy:
            doc_copy["_id"] = str(doc_copy["_id"])
            doc_copy["id"] = doc_copy["_id"]
        if hasattr(self.model_cls, "from_mongo"):
            return self.model_cls.from_mongo(doc_copy)
        return self.model_cls(**doc_copy)

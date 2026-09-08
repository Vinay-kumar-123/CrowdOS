"""
User Repository — Sprint 15.

Provides MongoDB persistence operations for the users collection:
- find_by_email
- find_by_id
- create_user
- update_last_login
- update_status
- list_users
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from app.models.user import UserDBModel, ensure_utc_datetime

logger = logging.getLogger("crowdos.repositories.user")


class UserRepository:
    def __init__(self, collection=None):
        self.col = collection

    @property
    def is_available(self) -> bool:
        return self.col is not None

    async def find_by_email(self, email: str) -> Optional[UserDBModel]:
        if not self.is_available:
            return None
        norm_email = email.strip().lower()
        doc = await self.col.find_one({"email": norm_email})
        if not doc:
            return None
        return UserDBModel(**doc)

    async def find_by_id(self, user_id: str) -> Optional[UserDBModel]:
        if not self.is_available:
            return None
        doc = await self.col.find_one({"user_id": user_id})
        if not doc:
            return None
        return UserDBModel(**doc)

    async def create_user(self, user: UserDBModel) -> UserDBModel:
        if not self.is_available:
            raise RuntimeError("Database unavailable: cannot create user")
        doc = user.model_dump()
        await self.col.insert_one(doc)
        logger.info(f"Operator user created: user_id='{user.user_id}', email='{user.email}', role='{user.role}'")
        return user

    async def update_last_login(self, user_id: str, login_time: Optional[datetime] = None) -> None:
        if not self.is_available:
            return
        ts = login_time or datetime.now(timezone.utc)
        await self.col.update_one(
            {"user_id": user_id},
            {"$set": {"last_login_at": ts, "updated_at": ts}}
        )

    async def update_user_status(self, user_id: str, is_active: bool) -> Optional[UserDBModel]:
        if not self.is_available:
            return None
        now = datetime.now(timezone.utc)
        res = await self.col.find_one_and_update(
            {"user_id": user_id},
            {"$set": {"is_active": is_active, "updated_at": now}},
            return_document=True
        )
        if not res:
            return None
        return UserDBModel(**res)

    async def list_users(self, skip: int = 0, limit: int = 100) -> List[UserDBModel]:
        if not self.is_available:
            return []
        cursor = self.col.find({}).sort("created_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [UserDBModel(**d) for d in docs]

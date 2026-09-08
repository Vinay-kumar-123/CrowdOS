"""
User Database Model — Sprint 15.

Defines the operator user identity model:
- UserRole: SUPER_ADMIN, VENUE_ADMIN, OPERATOR, ANALYST
- UserDBModel: Persistent user document in MongoDB users collection

Privacy guarantee:
Zero face embeddings, biometric vectors, face crops, raw frames, or visitor identity tokens
are ever stored in user records. Strict recursive validation rejects prohibited fields.
"""
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Union
from pydantic import Field, model_validator
from app.models.base import BaseDBModel, utc_now
from app.models.event import PROHIBITED_BIOMETRIC_FIELDS

# Comprehensive list of prohibited biometric fields
PROHIBITED_USER_BIOMETRIC_FIELDS = PROHIBITED_BIOMETRIC_FIELDS | {
    "face_encoding",
    "face_encodings",
    "embeddings",
    "face_crops",
    "biometric_vectors",
    "raw_frames",
    "raw_images",
}


def ensure_utc_datetime(val: Union[datetime, str, None]) -> Optional[datetime]:
    """Ensure a timestamp is a timezone-aware UTC datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if isinstance(val, str):
        cleaned = val.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def _assert_no_biometrics_recursive(data: Any, path: str = "") -> None:
    """Recursively enforce that no prohibited biometric field is present."""
    if isinstance(data, dict):
        for k, v in data.items():
            current_path = f"{path}.{k}" if path else str(k)
            if str(k).lower() in PROHIBITED_USER_BIOMETRIC_FIELDS and v is not None:
                raise ValueError(
                    f"PRIVACY VIOLATION: Prohibited biometric field '{k}' found at '{current_path}'."
                )
            _assert_no_biometrics_recursive(v, current_path)
    elif isinstance(data, (list, tuple, set)):
        for idx, item in enumerate(data):
            _assert_no_biometrics_recursive(item, f"{path}[{idx}]")


class UserRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    VENUE_ADMIN = "VENUE_ADMIN"
    OPERATOR = "OPERATOR"
    ANALYST = "ANALYST"


class UserDBModel(BaseDBModel):
    """
    MongoDB document model for an operator user.
    """
    user_id: str = Field(..., description="Unique user identifier (UUID)")
    email: str = Field(..., description="Normalized lowercase unique email address")
    password_hash: str = Field(..., description="Bcrypt password hash ($2b$12$...)")
    display_name: str = Field(..., description="Operator display name")
    role: UserRole = Field(default=UserRole.OPERATOR, description="Assigned operator role")
    venue_ids: List[str] = Field(
        default_factory=list,
        description="List of authorized venue IDs (or ['*'] for SUPER_ADMIN)"
    )
    is_active: bool = Field(default=True, description="True if account is active and allowed to authenticate")
    last_login_at: Optional[datetime] = Field(default=None, description="Timestamp of latest successful login (UTC)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Safe non-biometric operational metadata")

    @model_validator(mode="before")
    @classmethod
    def validate_user_data(cls, data: Any):
        if isinstance(data, dict):
            _assert_no_biometrics_recursive(data)
            if "email" in data and isinstance(data["email"], str):
                data["email"] = data["email"].strip().lower()
            if "last_login_at" in data:
                data["last_login_at"] = ensure_utc_datetime(data["last_login_at"])
        return data

    @model_validator(mode="after")
    def validate_user_after(self):
        if hasattr(self, "__pydantic_extra__") and self.__pydantic_extra__:
            _assert_no_biometrics_recursive(self.__pydantic_extra__)
        return self

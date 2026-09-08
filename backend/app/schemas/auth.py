"""
Authentication Schemas — Sprint 15.

Defines Pydantic request and response models for operator authentication & user management:
- LoginRequest
- TokenResponse
- UserResponse
- UserCreateRequest
- UserStatusUpdateRequest

Privacy guarantee:
Zero biometric fields allowed. All schemas inherit from PrivacyValidatedModel or enforce
strict validation. Plaintext passwords or password hashes are never returned in responses.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, field_validator
from app.models.user import UserRole
from app.schemas.visitor_analytics import PrivacyValidatedModel


class LoginRequest(BaseModel):
    email: str = Field(..., description="Operator email address")
    password: str = Field(..., min_length=8, max_length=72, description="Operator password (max 72 bytes)")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(default=900, description="Token lifetime in seconds (15 min)")
    user: "UserResponse"


class UserResponse(PrivacyValidatedModel):
    user_id: str
    email: str
    display_name: str
    role: UserRole
    venue_ids: List[str]
    is_active: bool
    created_at: str
    last_login_at: Optional[str] = None


class UserCreateRequest(BaseModel):
    email: str = Field(..., description="Operator email address")
    password: str = Field(..., min_length=8, max_length=72, description="Initial password")
    display_name: str = Field(..., min_length=2, max_length=100)
    role: UserRole = Field(default=UserRole.OPERATOR)
    venue_ids: List[str] = Field(default_factory=list)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserStatusUpdateRequest(BaseModel):
    is_active: bool

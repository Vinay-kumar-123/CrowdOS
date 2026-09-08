"""
User Management Endpoints — Sprint 15.

Routes (Strictly restricted to SUPER_ADMIN):
- POST /v1/users              -> Provision a new operator user
- GET  /v1/users              -> List operator users
- PATCH /v1/users/{id}/status -> Activate or deactivate an operator user
"""
import uuid
import logging
from typing import List
from fastapi import APIRouter, Depends, Query
from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.user import UserDBModel, UserRole
from app.repositories.user_repository import UserRepository
from app.dependencies.database import get_user_repository
from app.dependencies.auth import require_role
from app.services.auth_service import hash_password
from app.schemas.auth import UserCreateRequest, UserResponse, UserStatusUpdateRequest
from app.api.v1.endpoints.auth import _format_user_response

logger = logging.getLogger("crowdos.api.users")

router = APIRouter(prefix="/v1/users", tags=["User Management"])


@router.post(
    "",
    response_model=UserResponse,
    status_code=201,
    summary="Create operator user",
    description="Provisions a new operator user. Restricted to SUPER_ADMIN.",
)
async def create_user(
    body: UserCreateRequest,
    admin_user: UserDBModel = Depends(require_role(UserRole.SUPER_ADMIN)),
    user_repo: UserRepository = Depends(get_user_repository),
):
    existing = await user_repo.find_by_email(body.email)
    if existing:
        raise ConflictException(f"User with email '{body.email}' already exists.")

    pw_hash = hash_password(body.password)
    new_user = UserDBModel(
        user_id=str(uuid.uuid4()),
        email=body.email,
        password_hash=pw_hash,
        display_name=body.display_name,
        role=body.role,
        venue_ids=body.venue_ids if body.role != UserRole.SUPER_ADMIN else ["*"],
        is_active=True,
    )
    created = await user_repo.create_user(new_user)
    return _format_user_response(created)


@router.get(
    "",
    response_model=List[UserResponse],
    status_code=200,
    summary="List operator users",
    description="Returns all registered operators. Restricted to SUPER_ADMIN.",
)
async def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    admin_user: UserDBModel = Depends(require_role(UserRole.SUPER_ADMIN)),
    user_repo: UserRepository = Depends(get_user_repository),
):
    users = await user_repo.list_users(skip=skip, limit=limit)
    return [_format_user_response(u) for u in users]


@router.patch(
    "/{user_id}/status",
    response_model=UserResponse,
    status_code=200,
    summary="Activate or deactivate operator user",
    description="Updates user active status. Restricted to SUPER_ADMIN.",
)
async def update_user_status(
    user_id: str,
    body: UserStatusUpdateRequest,
    admin_user: UserDBModel = Depends(require_role(UserRole.SUPER_ADMIN)),
    user_repo: UserRepository = Depends(get_user_repository),
):
    if admin_user.user_id == user_id and not body.is_active:
        raise ValidationException("Admins cannot deactivate their own account.")

    updated = await user_repo.update_user_status(user_id=user_id, is_active=body.is_active)
    if not updated:
        raise NotFoundException(f"User '{user_id}' not found.")
    return _format_user_response(updated)

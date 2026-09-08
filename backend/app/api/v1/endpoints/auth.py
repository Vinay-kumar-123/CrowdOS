"""
Authentication Endpoints — Sprint 15.

Routes:
- POST /v1/auth/login    -> Validates credentials, issues JWT token, sets HttpOnly cookie
- POST /v1/auth/logout   -> Revokes token jti in Redis/local cache, clears cookie
- GET  /v1/auth/me       -> Returns current authenticated user profile
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Response, Request, Header, Cookie
from app.core.settings import settings
from app.models.user import UserDBModel
from app.repositories.user_repository import UserRepository
from app.dependencies.database import get_user_repository
from app.services.auth_service import AuthService
from app.dependencies.auth import get_current_active_user, _get_auth_service
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse

logger = logging.getLogger("crowdos.api.auth")

router = APIRouter(prefix="/v1/auth", tags=["Authentication"])


def _format_user_response(user: UserDBModel) -> UserResponse:
    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        venue_ids=user.venue_ids,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if hasattr(user.created_at, "isoformat") else str(user.created_at),
        last_login_at=user.last_login_at.isoformat() if user.last_login_at and hasattr(user.last_login_at, "isoformat") else None,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=200,
    summary="Operator login",
    description="Authenticates operator credentials, sets an HttpOnly access_token cookie, and returns a JWT bearer token.",
)
async def login(
    body: LoginRequest,
    response: Response,
    auth_svc: AuthService = Depends(_get_auth_service),
):
    user = await auth_svc.authenticate_user(email=body.email, plain_password=body.password)
    token, jti, expires_in = auth_svc.create_access_token(user)

    # Set HttpOnly/Secure/SameSite cookie
    is_secure = settings.ENVIRONMENT.lower() not in ("development", "test", "testing")
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=expires_in,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/",
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        user=_format_user_response(user),
    )


@router.post(
    "/logout",
    status_code=200,
    summary="Operator logout",
    description="Revokes the current JWT access token jti and deletes the session cookie.",
)
async def logout(
    response: Response,
    authorization: Optional[str] = Header(default=None),
    access_token: Optional[str] = Cookie(default=None),
    user: UserDBModel = Depends(get_current_active_user),
    auth_svc: AuthService = Depends(_get_auth_service),
):
    token: Optional[str] = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    if not token and access_token:
        token = access_token

    if token:
        await auth_svc.revoke_token(token)

    # Clear cookie
    response.delete_cookie(key="access_token", path="/")
    return {"message": "Successfully logged out."}


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=200,
    summary="Get current user profile",
    description="Returns the profile and authorized venue scope for the authenticated operator.",
)
async def get_me(user: UserDBModel = Depends(get_current_active_user)):
    return _format_user_response(user)

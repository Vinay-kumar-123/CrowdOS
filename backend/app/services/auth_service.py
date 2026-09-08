"""
Authentication Service — Sprint 15.

Coordinates:
- Secure password hashing & verification via bcrypt (work factor 12)
- JWT access token generation & decoding with PyJWT (HS256)
- Unique jti generation on token issuance
- Token revocation tracking via Redis (with in-memory LRU/TTL fallback)
- Brute-force rate limiting on login attempts
"""
import uuid
import time
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt

from app.core.settings import settings
from app.core.exceptions import (
    AuthenticationException,
    AuthorizationException,
    RateLimitException,
    ValidationException,
)
from app.models.user import UserDBModel, UserRole
from app.repositories.user_repository import UserRepository
from app.database.redis.connection import redis_connection

logger = logging.getLogger("crowdos.services.auth")

# In-memory revocation cache for degraded mode when Redis is unavailable: {jti: expire_epoch}
_local_revoked_jtis: Dict[str, float] = {}

# In-memory rate limiting cache: {key: [timestamp, ...]}
_local_rate_limit: Dict[str, list] = {}


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with work factor 12."""
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) > 72:
        raise ValidationException("Password exceeds maximum length of 72 bytes.")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pw_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time verification of password against bcrypt hash."""
    try:
        pw_bytes = plain_password.encode("utf-8")
        if len(pw_bytes) > 72:
            return False
        return bcrypt.checkpw(pw_bytes, hashed_password.encode("utf-8"))
    except Exception as e:
        logger.debug(f"Password verification error: {e}")
        return False


class AuthService:
    def __init__(self, user_repo: UserRepository, redis_client=None):
        self.user_repo = user_repo
        self.redis = redis_client

    def _get_secret_key(self) -> str:
        key = settings.SECRET_KEY
        if not key or len(key) < 32:
            # Enforce 32-byte key for security
            if settings.ENVIRONMENT != "development":
                raise RuntimeError("CRITICAL: CROWDOS_SECRET_KEY must be at least 32 bytes.")
            key = key.ljust(32, "x")
        return key

    async def check_rate_limit(self, identifier: str) -> None:
        """Enforce brute-force protection: max N attempts in window seconds."""
        max_attempts = settings.AUTH_RATE_LIMIT_MAX_ATTEMPTS
        window_seconds = settings.AUTH_RATE_LIMIT_WINDOW_SECONDS
        key = f"crowdos:auth:ratelimit:{identifier.strip().lower()}"

        client = self.redis or (redis_connection.get_client() if redis_connection.is_connected else None)
        if client:
            try:
                current_val = await client.incr(key)
                if current_val == 1:
                    await client.expire(key, window_seconds)
                if current_val > max_attempts:
                    raise RateLimitException("Too many login attempts. Please wait 60 seconds.")
                return
            except RateLimitException:
                raise
            except Exception as e:
                logger.warning(f"Redis rate limit failure: {e}. Falling back to in-memory window.")

        # In-memory fallback
        now = time.time()
        attempts = _local_rate_limit.get(key, [])
        valid_attempts = [t for t in attempts if now - t < window_seconds]
        if len(valid_attempts) >= max_attempts:
            raise RateLimitException("Too many login attempts. Please wait 60 seconds.")
        valid_attempts.append(now)
        _local_rate_limit[key] = valid_attempts

    async def clear_rate_limit(self, identifier: str) -> None:
        """Clear rate limit counter upon successful authentication."""
        key = f"crowdos:auth:ratelimit:{identifier.strip().lower()}"
        client = self.redis or (redis_connection.get_client() if redis_connection.is_connected else None)
        if client:
            try:
                await client.delete(key)
            except Exception:
                pass
        _local_rate_limit.pop(key, None)

    def create_access_token(self, user: UserDBModel) -> Tuple[str, str, int]:
        """
        Mint a new HS256 JWT access token with unique jti.
        Returns: (token_str, jti, expires_in_seconds)
        """
        now = datetime.now(timezone.utc)
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        exp = now + expires_delta
        expires_in = int(expires_delta.total_seconds())
        jti = uuid.uuid4().hex

        payload = {
            "sub": user.user_id,
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "venue_ids": user.venue_ids,
            "jti": jti,
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }

        secret = self._get_secret_key()
        token = jwt.encode(payload, secret, algorithm=settings.JWT_ALGORITHM)
        return token, jti, expires_in

    async def revoke_token(self, token: str) -> None:
        """Blacklist a token by recording its jti in Redis (or in-memory cache) with TTL."""
        try:
            secret = self._get_secret_key()
            payload = jwt.decode(
                token,
                secret,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": False}  # allow extracting claims even if near expiry
            )
            jti = payload.get("jti")
            exp = payload.get("exp", 0)
            if not jti:
                return

            remaining_ttl = max(1, int(exp - time.time()))
            client = self.redis or (redis_connection.get_client() if redis_connection.is_connected else None)
            if client:
                try:
                    await client.set(f"crowdos:auth:revoked_jti:{jti}", "revoked", ex=remaining_ttl)
                except Exception as e:
                    logger.warning(f"Redis revocation set failed: {e}. Falling back to memory.")
                    _local_revoked_jtis[jti] = time.time() + remaining_ttl
            else:
                _local_revoked_jtis[jti] = time.time() + remaining_ttl

            # Clean expired items in local cache
            now = time.time()
            expired_keys = [k for k, v in _local_revoked_jtis.items() if v < now]
            for k in expired_keys:
                _local_revoked_jtis.pop(k, None)

        except Exception as e:
            logger.warning(f"Token revocation error: {e}")

    async def is_token_revoked(self, jti: str) -> bool:
        """Check if jti has been invalidated via logout."""
        if not jti:
            return False

        # Check local cache first
        if jti in _local_revoked_jtis:
            if _local_revoked_jtis[jti] >= time.time():
                return True
            else:
                _local_revoked_jtis.pop(jti, None)

        # Check Redis
        client = self.redis or (redis_connection.get_client() if redis_connection.is_connected else None)
        if client:
            try:
                val = await client.get(f"crowdos:auth:revoked_jti:{jti}")
                return val is not None
            except Exception as e:
                logger.warning(f"Redis revocation check warning: {e}")
                return False

        return False

    async def authenticate_user(self, email: str, plain_password: str) -> UserDBModel:
        """
        Authenticate operator credentials with rate limiting and constant-time check.
        Generic failure message to prevent email discovery.
        """
        await self.check_rate_limit(email)

        norm_email = email.strip().lower()
        user = await self.user_repo.find_by_email(norm_email)

        # Constant-time dummy verification if user does not exist
        if not user:
            # Dummy hash matching standard bcrypt to ensure constant-time response
            dummy_hash = "$2b$12$e8Y5M5R8HjG0qBv4WlK7gOHQ1D1k.OqA9Lz1mU7lUq3k1b9yY6e6q"
            verify_password(plain_password, dummy_hash)
            raise AuthenticationException("Invalid email or password.")

        if not user.is_active:
            raise AuthenticationException("Account is deactivated. Contact an administrator.")

        if not verify_password(plain_password, user.password_hash):
            raise AuthenticationException("Invalid email or password.")

        # Success: clear rate limit counter and update last login
        await self.clear_rate_limit(email)
        await self.user_repo.update_last_login(user.user_id)
        return user

    async def verify_token_and_get_user(self, token: str) -> UserDBModel:
        """
        Validate JWT token, verify non-revoked, and fetch active user from MongoDB.
        """
        secret = self._get_secret_key()
        try:
            payload = jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise AuthenticationException("Token has expired.")
        except jwt.InvalidTokenError as e:
            raise AuthenticationException("Invalid token.")

        if payload.get("type") != "access":
            raise AuthenticationException("Invalid token type.")

        jti = payload.get("jti")
        if await self.is_token_revoked(jti):
            raise AuthenticationException("Token has been revoked.")

        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationException("Invalid token claims.")

        user = await self.user_repo.find_by_id(user_id)
        if not user or not user.is_active:
            raise AuthenticationException("User not found or account is deactivated.")

        return user

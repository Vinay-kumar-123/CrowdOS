"""
Redis Asynchronous Connection Manager — Sprint 10.

Manages connection lifecycle with Upstash Redis / standard Redis using redis.asyncio,
safe credential masking in logs, startup health ping, and graceful degradation.
"""
import re
import logging
from typing import Optional
import redis.asyncio as redis
from app.core.logger import logger
from app.database.redis.config import REDIS_URL


def mask_redis_uri(uri: str) -> str:
    """
    Mask password in Redis URI for safe logging.
    e.g. redis://:pass@host:6379 or rediss://default:pass@host:6379
    """
    if not uri:
        return ""
    return re.sub(r":([^@/]+)@", r":***@", uri)


class RedisConnection:
    client: Optional[redis.Redis] = None
    _is_healthy: bool = False

    @property
    def is_connected(self) -> bool:
        return self.client is not None and self._is_healthy

    def get_client(self) -> Optional[redis.Redis]:
        return self.client


redis_connection = RedisConnection()


async def connect_to_mongo_and_redis_ping():
    """Helper to verify connections."""
    pass


async def connect_to_redis() -> None:
    """
    Configure and establish asynchronous Redis connection (supports Upstash rediss://).
    Verifies connectivity with PING and handles outages gracefully.
    """
    masked_url = mask_redis_uri(REDIS_URL)
    logger.info(f"Connecting to Redis at {masked_url}...")
    try:
        client = redis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        # Verify connection with ping
        pong = await client.ping()
        if pong:
            redis_connection.client = client
            redis_connection._is_healthy = True
            logger.info("Successfully connected to Redis (PING OK).")
    except Exception as e:
        logger.warning(
            f"Could not establish connection to Redis: {e}. "
            "Backend will operate in degraded mode for cache/fast state."
        )
        redis_connection.client = None
        redis_connection._is_healthy = False


async def close_redis_connection() -> None:
    """
    Gracefully close Redis client connection.
    """
    if redis_connection.client:
        logger.info("Closing Redis connection...")
        try:
            await redis_connection.client.aclose()
        except Exception as e:
            logger.debug(f"Error closing Redis client: {e}")
        finally:
            redis_connection.client = None
            redis_connection._is_healthy = False
            logger.info("Redis connection closed.")

import redis.asyncio as redis
from app.core.logger import logger
from app.database.redis.config import REDIS_URL


class RedisConnection:
    client: redis.Redis = None


redis_connection = RedisConnection()


async def connect_to_redis() -> None:
    """
    Configure Redis async client connection.
    No active operations are executed in MVP scaffold.
    """
    logger.info(f"Configuring Redis connection for URL: {REDIS_URL}...")
    try:
        redis_connection.client = redis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
        )
        logger.info("Redis client configured successfully.")
    except Exception as e:
        logger.warning(f"Redis client initialization deferred: {e}")
        redis_connection.client = None


async def close_redis_connection() -> None:
    """
    Close Redis client connection.
    """
    if redis_connection.client:
        logger.info("Closing Redis connection...")
        await redis_connection.client.close()
        logger.info("Redis connection closed.")

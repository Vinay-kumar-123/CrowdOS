"""
FastAPI Lifespan Startup & Shutdown Event Handlers — Sprint 11.
"""
from typing import Callable
from app.core.logger import logger
from app.database.mongodb.connection import connect_to_mongo, close_mongo_connection
from app.database.redis.connection import connect_to_redis, close_redis_connection
from app.realtime.broadcaster import broadcaster


def create_start_app_handler() -> Callable:
    async def start_app() -> None:
        logger.info("Starting CrowdOS Backend application...")
        await connect_to_mongo()
        await connect_to_redis()
        await broadcaster.start_redis_listener()
        logger.info("CrowdOS Backend application started successfully.")
    return start_app


def create_stop_app_handler() -> Callable:
    async def stop_app() -> None:
        logger.info("Stopping CrowdOS Backend application...")
        await broadcaster.stop_redis_listener()
        await close_redis_connection()
        await close_mongo_connection()
        logger.info("CrowdOS Backend application stopped cleanly.")
    return stop_app

from typing import Callable
from app.core.logger import logger
from app.database.mongodb.connection import connect_to_mongo, close_mongo_connection
from app.database.redis.connection import connect_to_redis, close_redis_connection


def create_start_app_handler() -> Callable:
    async def start_app() -> None:
        logger.info("Starting CrowdOS Backend application...")
        await connect_to_mongo()
        await connect_to_redis()
        logger.info("CrowdOS Backend application started successfully.")
    return start_app


def create_stop_app_handler() -> Callable:
    async def stop_app() -> None:
        logger.info("Stopping CrowdOS Backend application...")
        await close_redis_connection()
        await close_mongo_connection()
        logger.info("CrowdOS Backend application stopped cleanly.")
    return stop_app

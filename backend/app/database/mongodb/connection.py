"""
MongoDB Asynchronous Connection Manager — Sprint 10.

Manages connection lifecycle with Motor (AsyncIOMotorClient), connection pooling,
safe credential masking in logs, startup health ping, index initialization,
and graceful degradation.
"""
import re
import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.logger import logger
from app.database.mongodb.config import MONGODB_URL, MONGODB_DATABASE
from app.database.mongodb.indexes import create_all_indexes


def mask_mongodb_uri(uri: str) -> str:
    """
    Mask password in MongoDB URI for safe logging.
    e.g. mongodb://user:pass@host:27017 -> mongodb://user:***@host:27017
    """
    if not uri:
        return ""
    return re.sub(r":([^@/]+)@", r":***@", uri)


class MongoDBConnection:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    _is_healthy: bool = False

    @property
    def is_connected(self) -> bool:
        return self.client is not None and self.db is not None and self._is_healthy

    def get_database(self) -> Optional[AsyncIOMotorDatabase]:
        return self.db

    def get_collection(self, name: str):
        if self.db is not None:
            return self.db[name]
        return None


db_connection = MongoDBConnection()


async def connect_to_mongo() -> None:
    """
    Establish asynchronous connection to MongoDB using Motor driver.
    Initializes connection pool, pings server, and ensures collection indexes.
    """
    masked_url = mask_mongodb_uri(MONGODB_URL)
    logger.info(f"Connecting to MongoDB at {masked_url}...")
    try:
        client = AsyncIOMotorClient(
            MONGODB_URL,
            maxPoolSize=100,
            minPoolSize=10,
            serverSelectionTimeoutMS=3000,
            connectTimeoutMS=3000,
            socketTimeoutMS=5000,
        )
        # Verify connection with ping
        await client.admin.command("ping")
        db = client[MONGODB_DATABASE]

        db_connection.client = client
        db_connection.db = db
        db_connection._is_healthy = True
        logger.info(f"Successfully connected to MongoDB database: '{MONGODB_DATABASE}'.")

        # Initialize indexes on startup
        await create_all_indexes(db)

    except Exception as e:
        logger.warning(
            f"Could not establish connection to MongoDB: {e}. "
            "Backend will operate in degraded (in-memory only) mode."
        )
        db_connection.client = None
        db_connection.db = None
        db_connection._is_healthy = False


async def close_mongo_connection() -> None:
    """
    Gracefully close MongoDB connection and cleanup pool.
    """
    if db_connection.client:
        logger.info("Closing MongoDB connection...")
        db_connection.client.close()
        db_connection.client = None
        db_connection.db = None
        db_connection._is_healthy = False
        logger.info("MongoDB connection closed.")

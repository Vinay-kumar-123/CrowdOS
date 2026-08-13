from motor.motor_asyncio import AsyncIOMotorClient
from app.core.logger import logger
from app.database.mongodb.config import MONGODB_URL, MONGODB_DATABASE


class MongoDBConnection:
    client: AsyncIOMotorClient = None
    db = None


db_connection = MongoDBConnection()


async def connect_to_mongo() -> None:
    """
    Establish asynchronous connection to MongoDB using Motor driver.
    """
    logger.info(f"Connecting to MongoDB at {MONGODB_URL}...")
    try:
        db_connection.client = AsyncIOMotorClient(
            MONGODB_URL,
            maxPoolSize=100,
            minPoolSize=10,
            serverSelectionTimeoutMS=5000,
        )
        db_connection.db = db_connection.client[MONGODB_DATABASE]
        logger.info(f"Successfully connected to MongoDB database: '{MONGODB_DATABASE}'.")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        # Soft failure logging for template initialization without active DB process
        db_connection.client = None
        db_connection.db = None


async def close_mongo_connection() -> None:
    """
    Close MongoDB connection.
    """
    if db_connection.client:
        logger.info("Closing MongoDB connection...")
        db_connection.client.close()
        logger.info("MongoDB connection closed.")

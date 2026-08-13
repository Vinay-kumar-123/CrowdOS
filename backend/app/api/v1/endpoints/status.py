from fastapi import APIRouter
from app.schemas.responses import StatusResponse
from app.core.settings import settings
from app.database.mongodb.connection import db_connection
from app.database.redis.connection import redis_connection

router = APIRouter()


@router.get("/status", response_model=StatusResponse, tags=["System Status"])
async def get_system_status():
    """
    Detailed system and infrastructure service connectivity status.
    """
    return StatusResponse(
        status="operational",
        environment=settings.ENVIRONMENT,
        database_connected=db_connection.db is not None,
        redis_configured=redis_connection.client is not None,
        version=settings.VERSION,
    )

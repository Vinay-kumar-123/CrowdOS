from datetime import datetime, timezone
from fastapi import APIRouter
from app.schemas.responses import HealthResponse, ReadyResponse
from app.core.settings import settings
from app.database.mongodb.connection import db_connection
from app.database.redis.connection import redis_connection
from app.services.camera_pipeline_service import camera_ai_pipeline
from app.services.camera_runtime_service import camera_runtime_service

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def get_health():
    """
    Health check endpoint for container orchestrators and load balancers.
    """
    return HealthResponse(
        status="healthy",
        service=settings.PROJECT_NAME,
        version=settings.VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/ready", response_model=ReadyResponse, tags=["Health"])
async def get_readiness():
    """
    Readiness probe verifying database, redis, AI vision pipeline, and camera runtime.
    """
    mongo_ok = bool(db_connection and db_connection.is_connected)
    redis_ok = bool(redis_connection and redis_connection.is_connected)
    ai_ok = bool(camera_ai_pipeline and camera_ai_pipeline.is_ready)
    camera_ok = bool(camera_runtime_service is not None)

    overall_ready = mongo_ok and redis_ok and ai_ok and camera_ok
    status_str = "ready" if overall_ready else "not_ready"

    return ReadyResponse(
        status=status_str,
        mongodb_connected=mongo_ok,
        redis_connected=redis_ok,
        ai_engine_ready=ai_ok,
        camera_runtime_ready=camera_ok,
        version=settings.VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

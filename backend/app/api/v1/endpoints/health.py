from datetime import datetime, timezone
from fastapi import APIRouter
from app.schemas.responses import HealthResponse
from app.core.settings import settings

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

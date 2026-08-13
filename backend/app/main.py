from fastapi import FastAPI
from app.core.settings import settings
from app.core.logger import logger
from app.core.events import create_start_app_handler, create_stop_app_handler
from app.middleware.cors import setup_cors
from app.middleware.logging import LoggingMiddleware
from app.api.v1.router import api_router
from app.websocket.router import ws_router
from app.schemas.responses import StandardResponse, HealthResponse, StatusResponse
from app.database.mongodb.connection import db_connection
from app.database.redis.connection import redis_connection
from datetime import datetime, timezone


def get_application() -> FastAPI:
    """
    Factory function to initialize FastAPI application instance.
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="CrowdOS Enterprise AI Crowd Intelligence Platform Backend API",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Middleware
    setup_cors(app)
    app.add_middleware(LoggingMiddleware)

    # Lifecycle Event Handlers
    app.add_event_handler("startup", create_start_app_handler())
    app.add_event_handler("shutdown", create_stop_app_handler())

    # Routers
    app.include_router(api_router, prefix="/api")
    app.include_router(ws_router)

    # Root Level Routes required by spec: GET /, GET /health, GET /api/status
    @app.get("/", response_model=StandardResponse, tags=["Root"])
    async def root():
        return StandardResponse(
            status="success",
            message="Welcome to CrowdOS API",
            data={
                "name": settings.PROJECT_NAME,
                "version": settings.VERSION,
                "environment": settings.ENVIRONMENT,
                "docs": "/docs"
            }
        )

    @app.get("/health", response_model=HealthResponse, tags=["Health Check"])
    async def root_health():
        return HealthResponse(
            status="healthy",
            service=settings.PROJECT_NAME,
            version=settings.VERSION,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @app.get("/api/status", response_model=StatusResponse, tags=["System Status"])
    async def root_status():
        return StatusResponse(
            status="operational",
            environment=settings.ENVIRONMENT,
            database_connected=db_connection.db is not None,
            redis_configured=redis_connection.client is not None,
            version=settings.VERSION,
        )

    return app


app = get_application()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )

from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.settings import settings
from app.core.logger import logger
from app.core.events import create_start_app_handler, create_stop_app_handler
from app.core.exceptions import CrowdOSException
from app.middleware.cors import setup_cors
from app.middleware.logging import LoggingMiddleware
from app.api.v1.router import api_router
from app.websocket.router import ws_router
from app.schemas.responses import StandardResponse, HealthResponse, StatusResponse
from app.database.mongodb.connection import db_connection
from app.database.redis.connection import redis_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_handler = create_start_app_handler()
    await start_handler()
    try:
        yield
    finally:
        stop_handler = create_stop_app_handler()
        await stop_handler()


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
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Middleware
    setup_cors(app)
    app.add_middleware(LoggingMiddleware)

    # Exception Handlers
    @app.exception_handler(CrowdOSException)
    async def crowdos_exception_handler(request: Request, exc: CrowdOSException):
        req_id = getattr(request.state, "request_id", "unknown")
        logger.warning(f"[{req_id}] Handled CrowdOSException ({exc.status_code}): {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "detail": exc.detail,
                "request_id": req_id,
            },
            headers={"X-Request-ID": req_id},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        req_id = getattr(request.state, "request_id", "unknown")
        logger.warning(f"[{req_id}] Validation error: {exc.errors()}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "status": "validation_error",
                "detail": exc.errors(),
                "request_id": req_id,
            },
            headers={"X-Request-ID": req_id},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        req_id = getattr(request.state, "request_id", "unknown")
        logger.error(f"[{req_id}] Unhandled server error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "server_error",
                "detail": "Internal server error occurred.",
                "request_id": req_id,
            },
            headers={"X-Request-ID": req_id},
        )

    # Routers
    app.include_router(api_router, prefix="/api")
    app.include_router(ws_router)

    # Root Level Routes required by spec: GET /, GET /health, GET /api/status
    @app.get(
        "/",
        response_model=StandardResponse,
        tags=["Root"],
        summary="Root API info",
        description="Returns API service information, environment, and documentation links.",
    )
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

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["Health Check"],
        summary="Service health probe",
        description="Liveness and readiness health probe for container orchestrators.",
    )
    async def root_health():
        return HealthResponse(
            status="healthy",
            service=settings.PROJECT_NAME,
            version=settings.VERSION,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @app.get(
        "/api/status",
        response_model=StatusResponse,
        tags=["System Status"],
        summary="System component status",
        description="Detailed infrastructure and connectivity status.",
    )
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

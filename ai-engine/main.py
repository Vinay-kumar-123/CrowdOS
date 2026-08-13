from datetime import datetime, timezone
from fastapi import FastAPI
from pydantic import BaseModel
from config.settings import ai_settings
from config.logging import ai_logger

app = FastAPI(
    title=ai_settings.SERVICE_NAME,
    version=ai_settings.VERSION,
    description="CrowdOS Standalone AI Vision Engine Service API",
)


class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str
    version: str
    device: str
    timestamp: str


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": ai_settings.SERVICE_NAME,
        "version": ai_settings.VERSION,
        "status": "online",
        "device": ai_settings.DEVICE,
    }


@app.get("/health", response_model=HealthResponse, tags=["Health Check"])
async def health():
    return HealthResponse(
        status="healthy",
        service=ai_settings.SERVICE_NAME,
        version=ai_settings.VERSION,
        device=ai_settings.DEVICE,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    import uvicorn
    ai_logger.info(f"Starting {ai_settings.SERVICE_NAME} on {ai_settings.HOST}:{ai_settings.PORT}...")
    uvicorn.run(
        "main:app",
        host=ai_settings.HOST,
        port=ai_settings.PORT,
        reload=True,
    )

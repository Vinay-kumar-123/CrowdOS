from typing import Any, Optional
from pydantic import BaseModel, Field


class StandardResponse(BaseModel):
    """
    Standardized API Response wrapper.
    """
    status: str = Field(default="success", description="Status code or string indicator")
    message: str = Field(default="Operation completed successfully", description="Human readable message")
    data: Optional[Any] = Field(default=None, description="Payload data")


class HealthResponse(BaseModel):
    """
    Health Check Response schema.
    """
    status: str = Field(default="healthy")
    service: str = Field(default="CrowdOS Backend API")
    version: str = Field(default="0.1.0")
    timestamp: str


class StatusResponse(BaseModel):
    """
    Detailed system status schema.
    """
    status: str = Field(default="operational")
    environment: str
    database_connected: bool
    redis_configured: bool
    version: str


class ReadyResponse(BaseModel):
    """
    Readiness probe schema for orchestrators and monitoring.
    """
    status: str = Field(default="ready", description="Overall readiness status ('ready' or 'not_ready')")
    mongodb_connected: bool = Field(..., description="MongoDB connectivity status")
    redis_connected: bool = Field(..., description="Redis connectivity status")
    ai_engine_ready: bool = Field(..., description="AI vision pipeline availability status")
    camera_runtime_ready: bool = Field(..., description="Camera runtime service status")
    version: str = Field(default="0.1.0")
    timestamp: str

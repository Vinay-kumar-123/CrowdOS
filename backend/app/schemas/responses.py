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

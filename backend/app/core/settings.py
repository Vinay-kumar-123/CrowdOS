from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings powered by Pydantic v2.
    Loads environment variables automatically.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    PROJECT_NAME: str = "CrowdOS Backend API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = True

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    MONGODB_URL: str = "mongodb://root:rootpassword@localhost:27017/crowdos_db?authSource=admin"
    MONGODB_DATABASE: str = "crowdos_db"

    REDIS_URL: str = "redis://:redispassword@localhost:6379/0"

    SECRET_KEY: str = "super-secret-crowdos-key-change-in-production"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)


settings = Settings()

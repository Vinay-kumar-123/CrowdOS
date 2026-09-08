from typing import List, Union
from pydantic import Field, AliasChoices, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings powered by Pydantic v2.
    Loads environment variables automatically.
    Supports CROWDOS_* and standard MONGODB_* environment variable naming conventions.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    PROJECT_NAME: str = Field(default="CrowdOS Backend API", validation_alias="CROWDOS_PROJECT_NAME")
    VERSION: str = Field(default="0.1.0", validation_alias="CROWDOS_VERSION")
    ENVIRONMENT: str = Field(default="development", validation_alias="CROWDOS_ENV")
    LOG_LEVEL: str = Field(default="INFO", validation_alias="CROWDOS_LOG_LEVEL")
    DEBUG: bool = Field(default=True, validation_alias="CROWDOS_DEBUG")

    HOST: str = Field(default="0.0.0.0", validation_alias="CROWDOS_API_HOST")
    PORT: int = Field(default=8000, validation_alias="CROWDOS_API_PORT")

    ENGINE_MODE: str = Field(default="in_memory", validation_alias="CROWDOS_ENGINE_MODE")

    MONGODB_URL: str = Field(
        default="mongodb://root:rootpassword@localhost:27017/crowdos_db?authSource=admin",
        validation_alias=AliasChoices(
            "CROWDOS_MONGODB_URL",
            "CROWDOS_MONGODB_URI",
            "MONGODB_URL",
            "MONGODB_URI",
        )
    )
    MONGODB_DATABASE: str = Field(
        default="crowdos_db",
        validation_alias=AliasChoices(
            "CROWDOS_MONGODB_DATABASE",
            "MONGODB_DATABASE",
            "MONGODB_DB",
        )
    )

    REDIS_URL: str = Field(
        default="redis://:redispassword@localhost:6379/0",
        validation_alias=AliasChoices(
            "CROWDOS_REDIS_URL",
            "CROWDOS_REDIS_URI",
            "REDIS_URL",
            "REDIS_URI",
        )
    )

    SECRET_KEY: str = Field(
        default="super-secret-crowdos-key-change-in-production",
        validation_alias="CROWDOS_SECRET_KEY"
    )
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        validation_alias="CROWDOS_CORS_ORIGINS"
    )

    VISITOR_HISTORY_RETENTION_DAYS: int = Field(
        default=30,
        ge=1,
        validation_alias=AliasChoices(
            "CROWDOS_VISITOR_RETENTION_DAYS",
            "VISITOR_HISTORY_RETENTION_DAYS",
        )
    )

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v_clean = v.strip()
            if v_clean.startswith("[") and v_clean.endswith("]"):
                import json
                try:
                    return json.loads(v_clean)
                except Exception:
                    pass
            return [i.strip() for i in v_clean.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        raise ValueError(v)


settings = Settings()

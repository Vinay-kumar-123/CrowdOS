from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    SERVICE_NAME: str = "CrowdOS AI Engine"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    HOST: str = "0.0.0.0"
    PORT: int = 8001

    DEVICE: str = "cpu"
    MODEL_PATH: str = "../models"
    BACKEND_API_URL: str = "http://localhost:8000"


ai_settings = AISettings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class CameraSettings(BaseSettings):
    """
    Environment-driven Configuration for the Camera Infrastructure Layer.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    MAX_CAMERAS: int = 100
    MAX_QUEUE_SIZE: int = 60
    FRAME_BUFFER_SIZE: int = 30
    RECONNECT_ATTEMPTS: int = 5
    RECONNECT_DELAY_SECONDS: float = 2.0
    FPS_LIMIT_DEFAULT: int = 30
    CAPTURE_TIMEOUT_SECONDS: float = 5.0
    HEALTH_CHECK_INTERVAL_SECONDS: float = 2.0
    QUEUE_BACKPRESSURE_POLICY: str = "DROP_OLDEST"  # DROP_OLDEST or DROP_NEWEST


camera_settings = CameraSettings()

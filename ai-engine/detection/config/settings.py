from pydantic_settings import BaseSettings, SettingsConfigDict


class DetectionSettings(BaseSettings):
    """
    Environment-driven Configuration for the AI Detection Engine.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    MODEL_PATH: str = "models/yolo11n.pt"
    MODEL_NAME: str = "yolo11n"
    CONFIDENCE_THRESHOLD: float = 0.45
    IOU_THRESHOLD: float = 0.45
    IMG_SIZE: int = 640
    DEVICE: str = "auto"  # auto, cuda, cpu, mps
    MAX_DETECTIONS: int = 300
    HALF_PRECISION: bool = False
    PERSON_CLASS_ID: int = 0
    WARMUP_ITERATIONS: int = 3


detection_settings = DetectionSettings()

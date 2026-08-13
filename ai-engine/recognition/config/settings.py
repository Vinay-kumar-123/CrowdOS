from pydantic_settings import BaseSettings, SettingsConfigDict


class RecognitionSettings(BaseSettings):
    """
    Environment-driven Configuration for the AI Face Recognition & Identity Association Engine.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    FACE_DETECTOR: str = "InsightFace"
    FACE_EMBEDDER: str = "InsightFace"
    FACE_RECOGNIZER: str = "InsightFace"
    MATCH_THRESHOLD: float = 0.60
    LOW_CONFIDENCE_THRESHOLD: float = 0.45
    MIN_FACE_CONFIDENCE: float = 0.50
    MIN_FACE_SIZE: int = 32           # Minimum face crop size (32x32 px)
    BLUR_THRESHOLD: float = 45.0      # Laplacian variance cutoff
    MIN_BRIGHTNESS: float = 40.0
    MAX_BRIGHTNESS: float = 220.0
    QUALITY_THRESHOLD: float = 0.50
    DEVICE: str = "auto"              # auto, cuda, cpu
    USE_GPU: bool = True
    EMBEDDING_DIMENSION: int = 512    # Standard 512-D InsightFace embedding
    TEMPORAL_CONFIRMATION_FRAMES: int = 3
    RECOGNITION_TIMEOUT: float = 5.0
    MAX_FACES_PER_TRACK: int = 1
    ALLOW_SYNTHETIC_FALLBACK: bool = False  # Production safety: synthetic embeddings disabled by default
    RECOGNIZER_VERSION: str = "5.0.0"


recognition_settings = RecognitionSettings()

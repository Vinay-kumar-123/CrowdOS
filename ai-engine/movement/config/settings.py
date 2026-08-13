from pydantic_settings import BaseSettings, SettingsConfigDict


class MovementSettings(BaseSettings):
    """
    Environment-driven Configuration for the Gate, Entry/Exit & Movement Intelligence Engine.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    TRAJECTORY_WINDOW: int = 8           # Number of historical points for direction/crossing
    MIN_DIRECTION_CONFIDENCE: float = 0.60
    ENTRY_CONFIRMATION_FRAMES: int = 2
    EXIT_CONFIRMATION_FRAMES: int = 2
    EVENT_DEDUP_WINDOW: float = 5.0      # Deduplication window in seconds
    MAX_TRACK_LOST_FRAMES: int = 30      # Max frames to retain track state during loss
    MIN_CROSSING_DISTANCE: float = 5.0   # Min movement displacement (pixels) to confirm line crossing
    OCCUPANCY_TIMEOUT: float = 3600.0    # Dwell timeout before stale inside journey cleanup
    DEFAULT_PAD_RATIO: float = 0.05
    ENGINE_VERSION: str = "6.0.0"


movement_settings = MovementSettings()

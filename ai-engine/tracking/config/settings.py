from pydantic_settings import BaseSettings, SettingsConfigDict


class TrackingSettings(BaseSettings):
    """
    Environment-driven Configuration for the AI Tracking Engine.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    TRACKER_TYPE: str = "ByteTrack"
    TRACK_THRESH: float = 0.5        # High confidence threshold for 1st stage association
    MIN_CONFIDENCE: float = 0.1      # Low confidence threshold for 2nd stage association
    MATCH_THRESHOLD: float = 0.8     # IoU match threshold for 1st stage association
    LOW_MATCH_THRESHOLD: float = 0.5 # IoU match threshold for 2nd stage association
    UNCONFIRMED_MATCH_THRESHOLD: float = 0.7 # IoU threshold for unconfirmed tracks
    MAX_LOST_FRAMES: int = 30        # Number of frames to keep lost tracks before removal
    FRAME_RATE: int = 30             # Video frame rate (FPS)
    MAXIMUM_TRACKS: int = 1000       # Maximum active tracklets allowed
    TRACKER_VERSION: str = "1.0.0"


tracking_settings = TrackingSettings()

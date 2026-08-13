from datetime import datetime, timezone


def get_utc_now() -> datetime:
    """
    Returns current timezone-aware UTC datetime.
    """
    return datetime.now(timezone.utc)

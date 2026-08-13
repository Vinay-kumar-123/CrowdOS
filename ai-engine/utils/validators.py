def validate_rtsp_url(url: str) -> bool:
    """
    RTSP stream URL validator shell.
    """
    return url.startswith("rtsp://") or url.startswith("http://") or url.startswith("https://")

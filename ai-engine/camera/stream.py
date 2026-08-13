class StreamManager:
    """
    Manages multiple concurrent IP camera RTSP streams.
    """
    def __init__(self):
        self.active_streams = {}

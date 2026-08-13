class FrameCapture:
    """
    RTSP / IP Camera frame stream capture abstraction.
    """
    def __init__(self, stream_url: str):
        self.stream_url = stream_url

    def read_frame(self):
        # Stub for camera stream reading
        return None

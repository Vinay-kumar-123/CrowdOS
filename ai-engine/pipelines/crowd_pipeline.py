from pipelines.base import BasePipeline


class CrowdMonitoringPipeline(BasePipeline):
    """
    Crowd monitoring pipeline combining detection, tracking, and counting.
    """
    def __init__(self):
        super().__init__()

    def process_frame(self, frame):
        # Pipeline orchestration stub
        return {
            "people_count": 0,
            "tracks": [],
        }

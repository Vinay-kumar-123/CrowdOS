from pipelines.base import BasePipeline


class EntryMonitoringPipeline(BasePipeline):
    """
    Dedicated Entry Gate Monitoring Pipeline.
    Tracks inward crowd flow rate and entry gate statistics.
    """
    def process_frame(self, frame):
        return {"pipeline": "entry", "count": 0}

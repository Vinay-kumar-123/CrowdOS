from pipelines.base import BasePipeline


class ExitMonitoringPipeline(BasePipeline):
    """
    Dedicated Exit Gate Monitoring Pipeline.
    Tracks outward crowd flow rate and exit gate throughput.
    """
    def process_frame(self, frame):
        return {"pipeline": "exit", "count": 0}

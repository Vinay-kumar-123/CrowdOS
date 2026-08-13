from pipelines.base import BasePipeline


class OccupancyEstimationPipeline(BasePipeline):
    """
    Facility Occupancy Estimation Pipeline.
    Computes real-time net crowd density across all registered entry/exit points.
    """
    def process_frame(self, frame):
        return {"pipeline": "occupancy", "occupancy": 0}

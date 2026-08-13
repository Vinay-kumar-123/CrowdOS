from pipelines.base import BasePipeline


class CameraProcessingPipeline(BasePipeline):
    """
    Per-Camera Dynamic Pipeline Runner.
    Executes configured analytics modules for a specific camera stream.
    """
    def process_frame(self, frame):
        return {"pipeline": "camera", "frame_id": 0}

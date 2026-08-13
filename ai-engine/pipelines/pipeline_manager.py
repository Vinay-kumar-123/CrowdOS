class PipelineManager:
    """
    Dynamic Orchestrator for vision pipelines per camera stream.
    """
    def __init__(self):
        self.active_pipelines = {}

    def register_pipeline(self, camera_id: str, pipeline):
        self.active_pipelines[camera_id] = pipeline

    def get_pipeline(self, camera_id: str):
        return self.active_pipelines.get(camera_id)

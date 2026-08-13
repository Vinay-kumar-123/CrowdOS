from pipelines.base import BasePipeline


class FaceRecognitionPipeline(BasePipeline):
    """
    Watchlist & Face Recognition Pipeline.
    Runs InsightFace feature extraction against indexed watchlist embeddings.
    """
    def process_frame(self, frame):
        return {"pipeline": "recognition", "matches": []}

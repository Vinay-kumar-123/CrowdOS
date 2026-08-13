class BasePipeline:
    """
    Abstract Base Pipeline class for processing vision stream frames.
    """
    def process_frame(self, frame):
        raise NotImplementedError

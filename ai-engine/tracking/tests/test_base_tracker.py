import pytest
from tracking.models.base_tracker import BaseTracker
from tracking.results.schema import TrackingResult


def test_base_tracker_abstract_instantiation():
    """
    Verify that BaseTracker cannot be instantiated directly without implementing abstract methods.
    """
    with pytest.raises(TypeError):
        BaseTracker()


class DummyCustomTracker(BaseTracker):
    """
    Dummy tracker implementing BaseTracker to verify inheritance contract.
    """
    def initialize(self) -> bool:
        return True

    def update(self, detection_result, frame=None) -> TrackingResult:
        return TrackingResult(
            frame_number=detection_result.frame_number,
            camera_id=detection_result.camera_id,
            tracking_time_ms=1.0,
            total_active_tracks=0,
            total_lost_tracks=0,
            tracks=[],
            tracker_name="DummyCustomTracker"
        )

    def reset(self) -> None:
        pass

    def destroy(self) -> None:
        pass

    def get_statistics(self) -> dict:
        return {"dummy": True}

    def health_check(self) -> bool:
        return True


def test_dummy_tracker_conformance(sample_frame_detection_result):
    tracker = DummyCustomTracker()
    assert tracker.initialize() is True
    res = tracker.update(sample_frame_detection_result)
    assert isinstance(res, TrackingResult)
    assert res.tracker_name == "DummyCustomTracker"
    assert tracker.health_check() is True

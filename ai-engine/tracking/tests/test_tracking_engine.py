import pytest
from tracking.engine.tracking_engine import TrackingEngine
from tracking.results.schema import TrackingResult
from tracking.tests.conftest import make_detection_result


def test_tracking_engine_process_detections():
    engine = TrackingEngine()
    det = make_detection_result(1, "cam_engine_01", [(50, 50, 150, 250, 0.80)])
    result = engine.process_detections(det)

    assert isinstance(result, TrackingResult)
    assert result.camera_id == "cam_engine_01"
    assert len(result.tracks) == 1
    assert result.tracks[0].confidence == 0.80


def test_tracking_engine_statistics_and_reset():
    engine = TrackingEngine()
    det1 = make_detection_result(1, "cam_stat", [(10, 10, 100, 200, 0.85)])
    engine.process_detections(det1)

    stats = engine.get_statistics("cam_stat")
    assert stats["active_tracks_count"] == 1
    assert stats["processed_frames"] == 1

    engine.reset_camera("cam_stat")
    stats_after_reset = engine.get_statistics("cam_stat")
    assert stats_after_reset["active_tracks_count"] == 0
    assert stats_after_reset["processed_frames"] == 0


def test_tracking_engine_health_check():
    engine = TrackingEngine()
    assert engine.health_check() is True

from tracking.engine.tracking_engine import TrackingEngine
from tracking.tests.conftest import make_detection_result


def test_multi_camera_state_isolation_and_independent_ids():
    """
    Verify CTO constraint:
    1. Each camera has an isolated tracker state.
    2. Track IDs are independent per camera (e.g. cam_A track '1' and cam_B track '1').
    """
    engine = TrackingEngine()

    # Camera A, Frame 1
    det_cam_a = make_detection_result(1, "camera_alpha", [(10, 10, 100, 200, 0.85)])
    res_a = engine.process_detections(det_cam_a)

    # Camera B, Frame 1
    det_cam_b = make_detection_result(1, "camera_beta", [(300, 300, 400, 500, 0.90)])
    res_b = engine.process_detections(det_cam_b)

    assert len(res_a.tracks) == 1
    assert len(res_b.tracks) == 1

    # Both independent camera instances start their internal track ID counter at '1'
    track_id_a = res_a.tracks[0].track_id
    track_id_b = res_b.tracks[0].track_id

    assert track_id_a == "1"
    assert track_id_b == "1"
    assert res_a.tracks[0].camera_id == "camera_alpha"
    assert res_b.tracks[0].camera_id == "camera_beta"

    # Reset camera_alpha, camera_beta state must remain untouched
    engine.reset_camera("camera_alpha")
    stats_a = engine.get_statistics("camera_alpha")
    stats_b = engine.get_statistics("camera_beta")

    assert stats_a["active_tracks_count"] == 0
    assert stats_b["active_tracks_count"] == 1

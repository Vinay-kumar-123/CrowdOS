import time
from camera.health.health_service import CameraHealthService


def test_health_service_metrics():
    health = CameraHealthService(camera_id="cam_001")
    assert health.status == "DISCONNECTED"
    assert health.calculate_health_percentage() == 0.0

    health.mark_connected()
    assert health.status == "CONNECTED"
    assert health.is_connected is True
    assert health.calculate_health_percentage() == 100.0

    # Record 5 synthetic frames
    now = time.time()
    for _ in range(5):
        health.record_frame(now)

    report = health.get_health_report()
    assert report["total_frames_received"] == 5
    assert report["healthy"] is True
    assert report["health_percentage"] == 100.0
    assert len(report["reconnect_history"]) >= 1

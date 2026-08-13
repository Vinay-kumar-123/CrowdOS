import concurrent.futures
from tracking.engine.tracking_engine import TrackingEngine
from tracking.tests.conftest import make_detection_result


def process_camera_stream(engine: TrackingEngine, camera_id: str, num_frames: int):
    """
    Simulate a worker thread ingesting video frames for a camera stream.
    """
    results = []
    for f in range(1, num_frames + 1):
        det = make_detection_result(f, camera_id, [(10 * f, 20 * f, 50 * f, 100 * f, 0.85)])
        res = engine.process_detections(det)
        results.append(res)
    return results


def test_concurrent_multi_camera_tracking():
    """
    Verify thread safety when 5 concurrent camera streams submit frames simultaneously.
    """
    engine = TrackingEngine()
    num_cameras = 5
    frames_per_cam = 20

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_cameras) as executor:
        futures = [
            executor.submit(process_camera_stream, engine, f"cam_thread_{i}", frames_per_cam)
            for i in range(num_cameras)
        ]
        completed_results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(completed_results) == num_cameras
    for stream_res in completed_results:
        assert len(stream_res) == frames_per_cam

    stats = engine.get_statistics()
    assert stats["active_cameras_count"] == num_cameras

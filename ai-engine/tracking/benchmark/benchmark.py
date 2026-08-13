import time
import uuid
import numpy as np
from typing import List, Dict, Any

from detection.results.schema import FrameDetectionResult, DetectionItem, BoundingBox
from tracking.engine.tracking_engine import TrackingEngine
from tracking.utils.logger import tracking_logger


def generate_synthetic_detections(
    num_persons: int,
    frame_number: int,
    camera_id: str = "benchmark_cam",
    noise: float = 2.0
) -> FrameDetectionResult:
    """
    Generate synthetic person detections moving across frames.
    """
    items: List[DetectionItem] = []
    np.random.seed(42 + frame_number)

    for i in range(num_persons):
        base_x = (i * 20.0 + frame_number * 3.0) % 600.0 + 20.0
        base_y = (i * 15.0 + frame_number * 1.5) % 400.0 + 20.0

        x1 = base_x + np.random.uniform(-noise, noise)
        y1 = base_y + np.random.uniform(-noise, noise)
        w = 40.0 + np.random.uniform(-1.0, 1.0)
        h = 100.0 + np.random.uniform(-2.0, 2.0)

        conf = float(np.clip(0.75 + np.random.uniform(-0.1, 0.2), 0.1, 0.99))

        item = DetectionItem(
            detection_id=str(uuid.uuid4()),
            class_id=0,
            class_name="person",
            confidence=conf,
            bbox=BoundingBox(x1=x1, y1=y1, x2=x1 + w, y2=y1 + h),
            center=(x1 + w / 2.0, y1 + h / 2.0),
            width=w,
            height=h
        )
        items.append(item)

    return FrameDetectionResult(
        frame_number=frame_number,
        camera_id=camera_id,
        inference_time_ms=5.0,
        total_persons_detected=len(items),
        detections=items,
        device_used="cpu",
        resolution=(1920, 1080)
    )


def run_benchmark(
    person_counts: List[int] = [10, 50, 100, 200],
    num_frames: int = 100
) -> Dict[str, Any]:
    """
    Execute performance benchmark of TrackingEngine across different track loads.
    """
    results = {}
    tracking_logger.info("=== STARTING TRACKING ENGINE BENCHMARK ===")

    for count in person_counts:
        engine = TrackingEngine()
        cam_id = f"cam_bench_{count}"
        latencies = []

        start_time = time.perf_counter()
        for f in range(num_frames):
            det_result = generate_synthetic_detections(count, frame_number=f, camera_id=cam_id)
            t0 = time.perf_counter()
            engine.process_detections(det_result)
            latencies.append((time.perf_counter() - t0) * 1000.0)

        total_time = time.perf_counter() - start_time
        avg_latency = float(np.mean(latencies))
        p95_latency = float(np.percentile(latencies, 95))
        fps = num_frames / total_time

        results[f"{count}_persons"] = {
            "num_persons": count,
            "total_frames": num_frames,
            "total_time_seconds": round(total_time, 3),
            "avg_latency_ms": round(avg_latency, 3),
            "p95_latency_ms": round(p95_latency, 3),
            "throughput_fps": round(fps, 2),
        }

        tracking_logger.info(
            f"Benchmark Load ({count} Persons): Avg Latency = {avg_latency:.2f}ms | P95 = {p95_latency:.2f}ms | Throughput = {fps:.2f} FPS"
        )

    return results


if __name__ == "__main__":
    benchmark_res = run_benchmark()
    print("Benchmark Results Summary:", benchmark_res)

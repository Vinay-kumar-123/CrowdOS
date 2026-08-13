"""
Sprint 3 — Person Detection Engine Benchmark Tool.
Measures FPS, inference latency, memory consumption, and GPU utilization.
"""
import time
import sys
import os
import statistics
import numpy as np

# Ensure ai-engine root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from detection.engine.detection_engine import DetectionEngine
from detection.utils.logger import detection_logger


def run_benchmark(num_frames: int = 100, resolution: tuple = (640, 480)) -> dict:
    """
    Runs synthetic frame inference benchmark for N frames.
    Returns aggregated timing & resource metrics.
    """
    print(f"\n{'='*60}")
    print(f"  CrowdOS Sprint 3 — Detection Engine Benchmark")
    print(f"  Frames: {num_frames} | Resolution: {resolution[0]}x{resolution[1]}")
    print(f"{'='*60}\n")

    engine = DetectionEngine()
    if not engine.initialize():
        print("[ERROR] Model failed to load. Aborting benchmark.")
        return {}

    inference_times_ms = []

    for i in range(num_frames):
        dummy_frame = np.random.randint(0, 255, (*resolution[::-1], 3), dtype=np.uint8)
        result = engine.detect_persons(frame=dummy_frame, camera_id="benchmark_cam", frame_number=i)
        inference_times_ms.append(result.inference_time_ms)

    # Compute aggregated metrics
    avg_ms = statistics.mean(inference_times_ms)
    min_ms = min(inference_times_ms)
    max_ms = max(inference_times_ms)
    p99_ms = sorted(inference_times_ms)[int(0.99 * len(inference_times_ms))]
    avg_fps = round(1000.0 / avg_ms, 2) if avg_ms > 0 else 0.0

    # Memory usage via psutil (optional)
    memory_mb = 0.0
    try:
        import psutil, os as _os
        process = psutil.Process(_os.getpid())
        memory_mb = round(process.memory_info().rss / 1024 / 1024, 2)
    except ImportError:
        pass

    # GPU memory (if CUDA available)
    gpu_memory_allocated_mb = 0.0
    gpu_memory_reserved_mb = 0.0
    try:
        import torch
        if torch.cuda.is_available():
            gpu_memory_allocated_mb = round(torch.cuda.memory_allocated() / 1024 / 1024, 2)
            gpu_memory_reserved_mb = round(torch.cuda.memory_reserved() / 1024 / 1024, 2)
    except ImportError:
        pass

    model_info = engine.model_manager.get_model_info()

    report = {
        "benchmark_frames": num_frames,
        "resolution": resolution,
        "model": model_info["model_name"],
        "device": model_info["device"],
        "avg_inference_ms": round(avg_ms, 2),
        "min_inference_ms": round(min_ms, 2),
        "max_inference_ms": round(max_ms, 2),
        "p99_inference_ms": round(p99_ms, 2),
        "avg_fps": avg_fps,
        "cpu_memory_mb": memory_mb,
        "gpu_memory_allocated_mb": gpu_memory_allocated_mb,
        "gpu_memory_reserved_mb": gpu_memory_reserved_mb,
    }

    print(f"  Average Inference : {report['avg_inference_ms']} ms")
    print(f"  Min Inference     : {report['min_inference_ms']} ms")
    print(f"  Max Inference     : {report['max_inference_ms']} ms")
    print(f"  P99 Latency       : {report['p99_inference_ms']} ms")
    print(f"  Average FPS       : {report['avg_fps']}")
    print(f"  CPU Memory        : {report['cpu_memory_mb']} MB")
    print(f"  GPU Memory (Alloc): {report['gpu_memory_allocated_mb']} MB")
    print(f"  GPU Memory (Rsrv) : {report['gpu_memory_reserved_mb']} MB")
    print(f"  Device            : {report['device']}")
    print(f"\n{'='*60}\n")

    return report


if __name__ == "__main__":
    run_benchmark(num_frames=100, resolution=(1280, 720))

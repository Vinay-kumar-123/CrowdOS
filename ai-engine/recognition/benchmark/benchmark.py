import time
import uuid
import numpy as np
from typing import List, Dict, Any

from recognition.models.insightface_recognizer import InsightFaceRecognizer
from recognition.models.in_memory_store import InMemoryIdentityStore
from recognition.engine.recognition_engine import RecognitionEngine
from recognition.utils.logger import recognition_logger


def make_synthetic_identity_store(num_identities: int = 5, dim: int = 512) -> InMemoryIdentityStore:
    """Create an in-memory store with synthetic L2-normalized reference embeddings."""
    store = InMemoryIdentityStore()
    rng = np.random.RandomState(42)
    for i in range(num_identities):
        identity_id = f"synthetic_person_{i+1:03d}"
        raw = rng.randn(dim).astype(np.float32)
        norm = np.linalg.norm(raw)
        vec = raw / norm if norm > 1e-6 else raw
        store.add_identity(identity_id, vec)
    return store


def make_synthetic_frame(height: int = 480, width: int = 640) -> np.ndarray:
    """Generate a blank BGR frame with a synthetic face-like region."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    # Add a light grey rectangle simulating a person region with a face
    frame[100:400, 220:420] = [180, 180, 180]   # Person body
    frame[110:200, 245:395] = [200, 170, 150]   # Face region
    return frame


def run_benchmark(
    face_counts: List[int] = [1, 5, 10, 25, 50],
    num_frames: int = 30
) -> Dict[str, Any]:
    """
    Synthetic benchmark measuring RecognitionEngine latency and FPS.

    IMPORTANT: Results are synthetic benchmarks only.
    Do NOT claim real-world camera performance from these results.
    """
    from tracking.results.schema import TrackingResult, TrackedPerson, TrackState
    from detection.results.schema import BoundingBox

    results = {}
    store = make_synthetic_identity_store(num_identities=10)

    recognition_logger.info("=== STARTING RECOGNITION ENGINE SYNTHETIC BENCHMARK ===")

    for count in face_counts:
        from recognition.models.insightface_embedder import InsightFaceEmbedder
        recognizer = InsightFaceRecognizer(embedder=InsightFaceEmbedder(allow_synthetic_fallback=True))
        engine = RecognitionEngine(recognizer, store)

        cam_id = f"bench_cam_{count}"
        latencies = []
        start_total = time.perf_counter()

        for f_idx in range(num_frames):
            # Synthesize TrackingResult with `count` tracks
            tracks = []
            for t_idx in range(count):
                x1 = float(10 + (t_idx * 15) % 500)
                y1 = float(50)
                x2 = x1 + 80.0
                y2 = 280.0
                tracks.append(TrackedPerson(
                    track_id=str(t_idx + 1),
                    detection_id=str(uuid.uuid4()),
                    camera_id=cam_id,
                    frame_number=f_idx + 1,
                    bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    confidence=0.90,
                    center=((x1 + x2) / 2, (y1 + y2) / 2),
                    track_state=TrackState.ACTIVE
                ))

            tracking_res = TrackingResult(
                frame_number=f_idx + 1,
                camera_id=cam_id,
                tracking_time_ms=2.0,
                total_active_tracks=count,
                total_lost_tracks=0,
                tracks=tracks
            )

            frame = make_synthetic_frame()
            t0 = time.perf_counter()
            engine.process_tracking_result(tracking_res, frame)
            latencies.append((time.perf_counter() - t0) * 1000.0)

        total_elapsed = time.perf_counter() - start_total
        avg_lat = float(np.mean(latencies))
        p95_lat = float(np.percentile(latencies, 95))
        fps = num_frames / total_elapsed

        results[f"{count}_faces"] = {
            "face_count": count,
            "total_frames": num_frames,
            "total_time_seconds": round(total_elapsed, 3),
            "avg_latency_ms": round(avg_lat, 2),
            "p95_latency_ms": round(p95_lat, 2),
            "throughput_fps": round(fps, 2),
            "note": "SYNTHETIC BENCHMARK — not real-world camera performance"
        }

        recognition_logger.info(
            f"Benchmark ({count} faces): avg={avg_lat:.1f}ms, p95={p95_lat:.1f}ms, fps={fps:.1f}"
        )

    return results


if __name__ == "__main__":
    benchmark_results = run_benchmark()
    for key, val in benchmark_results.items():
        print(f"{key}: {val}")

import time
import uuid
from typing import List, Dict, Any

from tracking.results.schema import TrackingResult, TrackedPerson, TrackState
from detection.results.schema import BoundingBox
from movement.config.gate_config import GateConfig, GateType, GateManager
from movement.engine.movement_engine import MovementEngine
from movement.utils.logger import movement_logger


def run_movement_benchmark(
    track_counts: List[int] = [1, 10, 50, 100],
    num_frames: int = 50
) -> Dict[str, Any]:
    """
    Synthetic benchmark measuring MovementEngine processing latency and FPS.

    IMPORTANT: Results are synthetic benchmarks only.
    Do NOT claim real-world camera performance from these results.
    """
    results = {}

    movement_logger.info("=== STARTING MOVEMENT ENGINE SYNTHETIC BENCHMARK ===")

    for count in track_counts:
        gate_mgr = GateManager()
        # Add virtual line gate
        gate_mgr.add_gate(GateConfig(
            gate_id=f"gate_bench_{count}",
            gate_name="Benchmark Main Gate",
            camera_id=f"cam_bench_{count}",
            gate_type=GateType.BIDIRECTIONAL,
            zone_type="LINE",
            zone_coordinates=[[100.0, 200.0], [500.0, 200.0]]
        ))

        engine = MovementEngine(gate_manager=gate_mgr)
        cam_id = f"cam_bench_{count}"

        latencies = []
        start_total = time.perf_counter()

        for f_idx in range(num_frames):
            tracks = []
            for t_idx in range(count):
                # Simulating track moving downwards across line y=200
                x = float(120 + (t_idx * 10) % 360)
                y = float(150 + f_idx * 4.0)  # Moves from y=150 to y=350 across y=200
                tracks.append(TrackedPerson(
                    track_id=str(t_idx + 1),
                    detection_id=str(uuid.uuid4()),
                    camera_id=cam_id,
                    frame_number=f_idx + 1,
                    bbox=BoundingBox(x1=x - 20, y1=y - 50, x2=x + 20, y2=y + 50),
                    confidence=0.90,
                    center=(x, y),
                    track_state=TrackState.ACTIVE
                ))

            tracking_res = TrackingResult(
                frame_number=f_idx + 1,
                camera_id=cam_id,
                tracking_time_ms=1.5,
                total_active_tracks=count,
                total_lost_tracks=0,
                tracks=tracks
            )

            t0 = time.perf_counter()
            engine.process_frame(tracking_res)
            latencies.append((time.perf_counter() - t0) * 1000.0)

        total_elapsed = time.perf_counter() - start_total
        avg_lat = float(sum(latencies) / len(latencies))
        fps = num_frames / total_elapsed

        results[f"{count}_tracks"] = {
            "track_count": count,
            "total_frames": num_frames,
            "total_time_seconds": round(total_elapsed, 3),
            "avg_latency_ms": round(avg_lat, 3),
            "throughput_fps": round(fps, 2),
            "events_generated": engine.metrics.total_events_generated,
            "note": "SYNTHETIC BENCHMARK — not real-world camera performance"
        }

        movement_logger.info(
            f"Movement Benchmark ({count} tracks): avg={avg_lat:.2f}ms, fps={fps:.1f}"
        )

    return results


if __name__ == "__main__":
    bench_res = run_movement_benchmark()
    for k, v in bench_res.items():
        print(f"{k}: {v}")

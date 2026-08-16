"""
PREDICTION ENGINE MICRO-BENCHMARK

Measures processing latency (avg, P95, P99), throughput (predictions/sec), and memory behavior.

DISCLAIMER:
  This benchmark measures in-memory Python engine performance ONLY.
  It does NOT represent:
    - RTSP camera throughput
    - YOLO inference speed
    - GPU inference performance
    - End-to-end CrowdOS deployment performance
    - Real-world crowd processing throughput
"""
import time
import math
import sys
import tracemalloc
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple

from prediction.engine.prediction_engine import PredictionEngine
from prediction.features.snapshot import PredictionInputSnapshot, GateInputSnapshot


def calculate_p95_p99(values: List[float]) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    sorted_v = sorted(values)
    n = len(sorted_v)
    idx_p95 = max(0, min(n - 1, math.ceil(0.95 * n) - 1))
    idx_p99 = max(0, min(n - 1, math.ceil(0.99 * n) - 1))
    return round(sorted_v[idx_p95], 3), round(sorted_v[idx_p99], 3)


def _make_snapshot(i: int, base_time: datetime) -> PredictionInputSnapshot:
    ts = (base_time + timedelta(seconds=i * 30)).isoformat()
    return PredictionInputSnapshot(
        session_id=f"bench-session-{i // 1000}",
        venue_id="bench-venue",
        timestamp=ts,
        session_status="ACTIVE",
        venue_capacity=1000,
        current_occupancy=min(950, 200 + (i % 500)),
        entry_rate_5m=float(10 + (i % 20)),
        exit_rate_5m=float(8 + (i % 15)),
        net_flow_rate_5m=float(2 + (i % 5)),
        entry_rate_15m=float(9 + (i % 10)),
        entry_rate_1m=float(12 + (i % 8)),
        density_level="MODERATE",
        congestion_level="BUILDING",
        occupancy_ratio=0.5 + (i % 10) * 0.03,
        average_dwell=600.0,
        p95_dwell=1200.0,
        gate_snapshots={
            "G1": GateInputSnapshot(gate_id="G1", entry_rate_5m=float(5 + (i % 10)), gate_occupancy=50),
            "G2": GateInputSnapshot(gate_id="G2", entry_rate_5m=float(3 + (i % 8)), gate_occupancy=30),
        }
    )


def run_prediction_benchmark(
    workloads: List[int] = [10, 100, 1000, 10000]
) -> Dict[str, Any]:
    results = {}
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    for count in workloads:
        engine = PredictionEngine(venue_id=f"venue_bench_{count}")
        latencies = []

        # Pre-generate snapshots to isolate engine execution time
        snapshots = [_make_snapshot(i, base_time) for i in range(count)]

        tracemalloc.start()
        start_total = time.perf_counter()

        for snap in snapshots:
            t0 = time.perf_counter()
            engine.predict(snap)
            latencies.append((time.perf_counter() - t0) * 1000.0)

        total_elapsed = time.perf_counter() - start_total
        _, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
        p95_lat, p99_lat = calculate_p95_p99(latencies)
        eps = count / total_elapsed if total_elapsed > 0 else 0.0

        res_item = {
            "input_count": count,
            "total_time_seconds": round(total_elapsed, 4),
            "avg_latency_ms": round(avg_lat, 3),
            "p95_latency_ms": p95_lat,
            "p99_latency_ms": p99_lat,
            "throughput_predictions_per_sec": round(eps, 2),
            "peak_memory_mb": round(peak_mem / 1024 / 1024, 2),
            "note": "PREDICTION ENGINE MICRO-BENCHMARK — in-memory Python logic only"
        }
        results[f"{count}_inputs"] = res_item
        print(f"Completed {count}_inputs: avg={avg_lat:.3f}ms, P95={p95_lat:.3f}ms, throughput={eps:.1f}/sec, peak_mem={peak_mem / 1024 / 1024:.2f}MB", flush=True)

    return results


if __name__ == "__main__":
    print("=" * 70, flush=True)
    print("CROWDOS SPRINT 8 — PREDICTION ENGINE MICRO-BENCHMARK", flush=True)
    print("=" * 70, flush=True)
    print("DISCLAIMER: In-memory Python engine only.", flush=True)
    print("Does NOT represent RTSP camera throughput, YOLO or GPU inference.", flush=True)
    print("=" * 70, flush=True)

    bench_results = run_prediction_benchmark()
    for key, val in bench_results.items():
        print(f"\n{key}:", flush=True)
        for k, v in val.items():
            print(f"  {k}: {v}", flush=True)

    sys.exit(0)

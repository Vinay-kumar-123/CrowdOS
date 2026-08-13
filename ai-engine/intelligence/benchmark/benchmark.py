"""
Synthetic Benchmark for CrowdOS Event Intelligence Engine.
Measures processing latency (avg, P95, P99), throughput (events/sec), and memory behavior.

IMPORTANT: Results represent ENGINE MICRO-BENCHMARK performance only.
Do NOT claim real-world camera system throughput based on this benchmark.
"""
import time
import math
import uuid
import sys
from datetime import datetime, timezone
from typing import List, Dict, Any

from movement.events.schema import EntryEvent, ExitEvent, MovementEventType
from movement.state.occupancy import OccupancyState
from intelligence.engine.intelligence_engine import EventIntelligenceEngine
from intelligence.utils.logger import intelligence_logger


def calculate_p95_p99(values: List[float]) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    sorted_v = sorted(values)
    n = len(sorted_v)
    idx_p95 = max(0, min(n - 1, math.ceil(0.95 * n) - 1))
    idx_p99 = max(0, min(n - 1, math.ceil(0.99 * n) - 1))
    return round(sorted_v[idx_p95], 3), round(sorted_v[idx_p99], 3)


def run_intelligence_benchmark(
    workloads: List[int] = [10, 100, 1000, 10000]
) -> Dict[str, Any]:
    results = {}
    intelligence_logger.info("=== STARTING INTELLIGENCE ENGINE SYNTHETIC BENCHMARK ===")

    for count in workloads:
        engine = EventIntelligenceEngine(venue_id=f"venue_bench_{count}")
        session = engine.session_manager.create_session(venue_id=f"venue_bench_{count}")
        engine.session_manager.start_session(session.session_id)

        latencies = []
        start_total = time.perf_counter()

        for idx in range(count):
            is_entry = (idx % 2 == 0)
            gate_id = f"gate_{(idx % 4) + 1}"
            ts = datetime.now(timezone.utc).isoformat()

            if is_entry:
                evt = EntryEvent(
                    camera_id=f"cam_{(idx % 2) + 1}",
                    gate_id=gate_id,
                    entry_gate_id=gate_id,
                    track_id=str(idx + 1),
                    detection_id=str(uuid.uuid4()),
                    identity_id=f"Person_{(idx % 10) + 1}" if idx % 3 == 0 else "UNKNOWN",
                    timestamp=ts
                )
            else:
                evt = ExitEvent(
                    camera_id=f"cam_{(idx % 2) + 1}",
                    gate_id=gate_id,
                    exit_gate_id=gate_id,
                    track_id=str(idx + 1),
                    detection_id=str(uuid.uuid4()),
                    identity_id=f"Person_{(idx % 10) + 1}" if idx % 3 == 0 else "UNKNOWN",
                    timestamp=ts,
                    dwell_time=float(10 + (idx % 300))
                )

            t0 = time.perf_counter()
            engine.process_event(evt)

            # Update occupancy state periodically
            if idx % 10 == 0:
                engine.process_occupancy_state(OccupancyState(
                    venue_id=f"venue_bench_{count}",
                    current_occupancy=max(0, (idx // 2) - (idx // 3)),
                    total_entries=(idx // 2) + 1,
                    total_exits=idx // 3,
                    gate_occupancy={gate_id: 5}
                ))

            latencies.append((time.perf_counter() - t0) * 1000.0)

        total_elapsed = time.perf_counter() - start_total
        avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
        p95_lat, p99_lat = calculate_p95_p99(latencies)
        eps = count / total_elapsed if total_elapsed > 0 else 0.0

        summary = engine.stop_session(session.session_id)

        results[f"{count}_events"] = {
            "event_count": count,
            "total_time_seconds": round(total_elapsed, 4),
            "avg_latency_ms": round(avg_lat, 3),
            "p95_latency_ms": p95_lat,
            "p99_latency_ms": p99_lat,
            "throughput_events_per_sec": round(eps, 2),
            "total_alerts": summary.total_alerts_created if summary else 0,
            "note": "ENGINE MICRO-BENCHMARK — not real-world camera system throughput"
        }

        intelligence_logger.info(
            f"Benchmark ({count} events): avg={avg_lat:.3f}ms, P95={p95_lat}ms, throughput={eps:.1f} events/sec"
        )

    return results


if __name__ == "__main__":
    bench_results = run_intelligence_benchmark()
    for key, val in bench_results.items():
        print(f"{key}: {val}")
    sys.exit(0)

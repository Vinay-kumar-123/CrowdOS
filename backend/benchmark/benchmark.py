"""
Local/In-memory development microbenchmark for CrowdOS FastAPI Backend.

Measures average latency, P95 latency, and throughput across 10, 100, and 1000 requests.
Labels: Local/In-memory development microbenchmark.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
logging.disable(logging.CRITICAL)

import time
import asyncio
import statistics
import tracemalloc
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.ai_engine_adapter import venue_registry


async def run_benchmark_batch(batch_size: int):
    venue_registry.clear_all()
    transport = ASGITransport(app=app)
    latencies_ms = []

    tracemalloc.start()
    mem_before, _ = tracemalloc.get_traced_memory()

    async with AsyncClient(transport=transport, base_url="http://benchmark") as client:
        # Setup venue and session
        init_res = await client.post(
            "/api/v1/venues/bench_venue/sessions",
            json={"venue_capacity": 5000}
        )
        session_id = init_res.json()["session_id"]
        await client.post(f"/api/v1/venues/bench_venue/sessions/{session_id}/start")

        start_total = time.perf_counter()

        for i in range(batch_size):
            t0 = time.perf_counter()
            if i % 2 == 0:
                resp = await client.post(
                    f"/api/v1/venues/bench_venue/sessions/{session_id}/events",
                    json={
                        "event_type": "ENTRY",
                        "gate_id": f"gate_{i % 4}",
                        "event_id": f"b_evt_{i}",
                    }
                )
            else:
                resp = await client.get(f"/api/v1/sessions/{session_id}/dashboard")

            t1 = time.perf_counter()
            if resp.status_code == 200:
                latencies_ms.append((t1 - t0) * 1000.0)

        total_elapsed = time.perf_counter() - start_total

    mem_after, mem_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    avg_lat = statistics.mean(latencies_ms) if latencies_ms else 0.0
    sorted_lat = sorted(latencies_ms)
    p95_idx = int(len(sorted_lat) * 0.95)
    p95_lat = sorted_lat[p95_idx] if sorted_lat else 0.0
    p50_idx = int(len(sorted_lat) * 0.50)
    p50_lat = sorted_lat[p50_idx] if sorted_lat else 0.0
    throughput = len(latencies_ms) / total_elapsed if total_elapsed > 0 else 0.0
    mem_delta_kb = (mem_after - mem_before) / 1024.0
    mem_peak_kb = mem_peak / 1024.0

    return {
        "batch_size": batch_size,
        "completed": len(latencies_ms),
        "total_elapsed_sec": round(total_elapsed, 4),
        "avg_latency_ms": round(avg_lat, 3),
        "p50_latency_ms": round(p50_lat, 3),
        "p95_latency_ms": round(p95_lat, 3),
        "throughput_req_per_sec": round(throughput, 1),
        "memory_delta_kb": round(mem_delta_kb, 1),
        "memory_peak_kb": round(mem_peak_kb, 1),
    }


async def main():
    print("=" * 70)
    print("CROWDOS BACKEND — LOCAL/IN-MEMORY DEVELOPMENT MICROBENCHMARK")
    print("=" * 70)

    for n in [10, 100, 1000]:
        res = await run_benchmark_batch(n)
        print(f"\n--- Batch Size: {n} Requests ---")
        print(f"  Completed:          {res['completed']}/{res['batch_size']}")
        print(f"  Total Duration:     {res['total_elapsed_sec']} s")
        print(f"  Average Latency:    {res['avg_latency_ms']} ms")
        print(f"  P50 Latency:        {res['p50_latency_ms']} ms")
        print(f"  P95 Latency:        {res['p95_latency_ms']} ms")
        print(f"  Throughput:         {res['throughput_req_per_sec']} req/sec")
        print(f"  Memory Delta:       {res['memory_delta_kb']} KB")
        print(f"  Peak Memory:        {res['memory_peak_kb']} KB")


if __name__ == "__main__":
    asyncio.run(main())

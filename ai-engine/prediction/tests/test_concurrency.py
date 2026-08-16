"""
test_concurrency.py — Tests for multi-threaded concurrency safety in PredictionEngine.
"""
import pytest
import threading
from prediction.engine.prediction_engine import PredictionEngine
from prediction.tests.conftest import make_snapshot, make_gate, make_ts


@pytest.fixture
def engine():
    e = PredictionEngine(venue_id="concurrency-venue")
    yield e
    e.reset()


def test_concurrent_predict_10_threads(engine):
    results = []
    errors = []

    def worker(thread_idx):
        try:
            snap = make_snapshot(
                session_id=f"session_{thread_idx}",
                timestamp=make_ts(thread_idx * 10),
                current_occupancy=100 + thread_idx * 20,
            )
            res = engine.predict(snap)
            results.append(res)
        except Exception as ex:
            errors.append(ex)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(results) == 10
    for r in results:
        assert r.status == "ok"


def test_concurrent_predict_50_threads(engine):
    results = []
    errors = []

    def worker(thread_idx):
        try:
            snap = make_snapshot(
                session_id=f"session_{thread_idx}",
                timestamp=make_ts(thread_idx * 5),
                current_occupancy=200 + (thread_idx % 10) * 15,
            )
            res = engine.predict(snap)
            results.append(res)
        except Exception as ex:
            errors.append(ex)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(results) == 50


def test_concurrent_predict_100_threads(engine):
    results = []
    errors = []

    def worker(thread_idx):
        try:
            snap = make_snapshot(
                session_id=f"session_{thread_idx}",
                timestamp=make_ts(thread_idx * 2),
                current_occupancy=300 + (thread_idx % 20) * 10,
                gate_snapshots={"G1": make_gate("G1", entry_rate=float(thread_idx % 5))},
            )
            res = engine.predict(snap)
            results.append(res)
        except Exception as ex:
            errors.append(ex)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(results) == 100
    metrics = engine.get_metrics()
    assert metrics["prediction_evaluations"] == 100

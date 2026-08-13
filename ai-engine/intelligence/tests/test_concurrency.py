"""
Concurrency & Thread-Safety Stress Tests for Event Intelligence Engine.
"""
import pytest
import threading
from intelligence.engine.intelligence_engine import EventIntelligenceEngine
from .conftest import make_entry_event, make_exit_event


def test_concurrent_event_ingestion(engine):
    session = engine.session_manager.create_session()
    engine.session_manager.start_session(session.session_id)

    num_threads = 8
    events_per_thread = 50

    def worker(thread_idx):
        for i in range(events_per_thread):
            track_id = f"{thread_idx}_{i}"
            evt = make_entry_event(gate_id=f"gate_{thread_idx}", track_id=track_id)
            engine.process_event(evt)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    summary = engine.stop_session(session.session_id)
    assert summary.total_entries == num_threads * events_per_thread


def test_concurrent_analytics_reads_and_writes(engine):
    session = engine.session_manager.create_session()
    engine.session_manager.start_session(session.session_id)

    stop_flag = False

    def writer():
        i = 0
        while not stop_flag:
            engine.process_event(make_entry_event(gate_id="gate_main", track_id=str(i)))
            i += 1

    def reader():
        while not stop_flag:
            intel = engine.get_current_intelligence()
            assert "flow" in intel
            assert "occupancy" in intel

    t_writer = threading.Thread(target=writer)
    t_reader = threading.Thread(target=reader)

    t_writer.start()
    t_reader.start()

    import time
    time.sleep(0.2)
    stop_flag = True

    t_writer.join()
    t_reader.join()

    assert engine.metrics.get_metrics()["events_processed"] > 0

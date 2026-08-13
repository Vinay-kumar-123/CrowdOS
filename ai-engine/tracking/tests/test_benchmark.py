from tracking.benchmark.benchmark import run_benchmark


def test_benchmark_execution():
    """
    Verify benchmark execution with reduced frame count for quick unit testing.
    """
    res = run_benchmark(person_counts=[5, 10], num_frames=10)
    assert "5_persons" in res
    assert "10_persons" in res
    assert res["5_persons"]["total_frames"] == 10
    assert res["5_persons"]["throughput_fps"] > 0.0

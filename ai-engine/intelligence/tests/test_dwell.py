"""
Tests for Aggregate Dwell Analytics (mean, median, P95, invalid/None handling).
"""
import pytest
from intelligence.analytics.dwell import DwellAnalytics, calculate_p95_nearest_rank


def test_dwell_analytics_basic_stats():
    dwell = DwellAnalytics()
    samples = [10.0, 20.0, 30.0, 40.0, 50.0]
    for s in samples:
        dwell.record_dwell(s)

    metrics = dwell.get_metrics()
    assert metrics.total_samples == 5
    assert metrics.average_dwell == 30.0
    assert metrics.median_dwell == 30.0
    assert metrics.min_dwell == 10.0
    assert metrics.max_dwell == 50.0


def test_dwell_p95_nearest_rank():
    # 20 samples: 10, 20, ..., 200
    samples = [float(i * 10) for i in range(1, 21)]
    # P95 index = ceil(0.95 * 20) - 1 = ceil(19) - 1 = 18 -> value 190.0
    p95 = calculate_p95_nearest_rank(samples)
    assert p95 == 190.0


def test_dwell_analytics_empty():
    dwell = DwellAnalytics()
    metrics = dwell.get_metrics()
    assert metrics.total_samples == 0
    assert metrics.average_dwell == 0.0
    assert metrics.median_dwell == 0.0
    assert metrics.p95_dwell == 0.0


def test_dwell_analytics_invalid_and_none_values():
    dwell = DwellAnalytics()
    assert not dwell.record_dwell(None)
    assert not dwell.record_dwell(-10.0)
    assert not dwell.record_dwell(float("nan"))
    assert not dwell.record_dwell(float("inf"))

    metrics = dwell.get_metrics()
    assert metrics.total_samples == 0

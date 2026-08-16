"""
test_trend.py — Tests for TrendDetector.
"""
import pytest
from prediction.trend.trend_detector import TrendDetector, _theil_sen_slope
from prediction.trend.trend_state import TrendDirection, TrendStrength


@pytest.fixture
def detector():
    return TrendDetector()


def test_theil_sen_slope_basic():
    # 1 point per 60 seconds (1 pt/min)
    points = [(0.0, 10.0), (60.0, 11.0), (120.0, 12.0), (180.0, 13.0)]
    slope = _theil_sen_slope(points)
    assert slope == pytest.approx(1.0, abs=0.01)


def test_theil_sen_slope_empty_or_single():
    assert _theil_sen_slope([]) is None
    assert _theil_sen_slope([(0.0, 10.0)]) is None


def test_theil_sen_slope_duplicates():
    points = [(0.0, 10.0), (0.0, 10.0)]
    slope = _theil_sen_slope(points)
    assert slope == pytest.approx(0.0)


def test_trend_insufficient_data(detector):
    detector.add_observation(10.0, 1000.0)
    detector.add_observation(12.0, 1030.0)  # only 2 observations (need 3)
    res = detector.detect("sess1", "ven1", "2026-01-01T12:00:30Z")
    assert res.direction == TrendDirection.INSUFFICIENT_DATA
    assert res.strength == TrendStrength.UNKNOWN
    assert res.slope is None


def test_trend_increasing(detector):
    # Risk score rising by 2 points every 30 seconds -> 4 points/min
    detector.add_observation(10.0, 1000.0)
    detector.add_observation(12.0, 1030.0)
    detector.add_observation(14.0, 1060.0)
    detector.add_observation(16.0, 1090.0)
    res = detector.detect("sess1", "ven1", "2026-01-01T12:01:30Z")
    assert res.direction == TrendDirection.INCREASING
    assert res.strength == TrendStrength.STRONG
    assert res.slope is not None
    assert res.slope > 0.5


def test_trend_decreasing(detector):
    # Risk score dropping
    detector.add_observation(50.0, 1000.0)
    detector.add_observation(45.0, 1030.0)
    detector.add_observation(40.0, 1060.0)
    detector.add_observation(35.0, 1090.0)
    res = detector.detect("sess1", "ven1", "2026-01-01T12:01:30Z")
    assert res.direction == TrendDirection.DECREASING
    assert res.slope < -0.5


def test_trend_stable(detector):
    # Constant risk score
    detector.add_observation(25.0, 1000.0)
    detector.add_observation(25.0, 1030.0)
    detector.add_observation(25.0, 1060.0)
    detector.add_observation(25.0, 1090.0)
    res = detector.detect("sess1", "ven1", "2026-01-01T12:01:30Z")
    assert res.direction == TrendDirection.STABLE
    assert res.slope == pytest.approx(0.0, abs=0.01)


def test_trend_out_of_order_timestamps(detector):
    detector.add_observation(16.0, 1090.0)
    detector.add_observation(10.0, 1000.0)
    detector.add_observation(14.0, 1060.0)
    detector.add_observation(12.0, 1030.0)
    res = detector.detect("sess1", "ven1", "2026-01-01T12:01:30Z")
    assert res.direction == TrendDirection.INCREASING
    assert res.slope > 0.0


def test_trend_reset(detector):
    detector.add_observation(10.0, 1000.0)
    detector.add_observation(12.0, 1030.0)
    detector.add_observation(14.0, 1060.0)
    detector.reset()
    res = detector.detect("sess1", "ven1", "2026-01-01T12:01:30Z")
    assert res.direction == TrendDirection.INSUFFICIENT_DATA
    assert res.n_observations == 0

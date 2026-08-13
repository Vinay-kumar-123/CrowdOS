"""
Tests for Crowd Density & Congestion Analytics (Thresholds, boundary conditions, validation).
"""
import pytest
from intelligence.config.thresholds import (
    CrowdThresholdConfig, CongestionThresholdConfig, CrowdDensityLevel, CongestionLevel
)
from intelligence.analytics.density import DensityAnalytics


def test_crowd_threshold_validation_valid():
    cfg = CrowdThresholdConfig(low_max=50, moderate_max=150, high_max=300, critical_min=301)
    assert cfg.low_max == 50


def test_crowd_threshold_validation_invalid_order():
    with pytest.raises(ValueError):
        CrowdThresholdConfig(low_max=100, moderate_max=50, high_max=300, critical_min=301)


def test_crowd_threshold_validation_negative():
    with pytest.raises(ValueError):
        CrowdThresholdConfig(low_max=-10, moderate_max=50, high_max=100, critical_min=101)


def test_exact_threshold_boundary_conditions():
    cfg = CrowdThresholdConfig(low_max=50, moderate_max=150, high_max=300, critical_min=301)

    # LOW boundary
    assert cfg.classify_occupancy(49) == CrowdDensityLevel.LOW
    assert cfg.classify_occupancy(50) == CrowdDensityLevel.LOW
    assert cfg.classify_occupancy(51) == CrowdDensityLevel.MODERATE

    # MODERATE boundary
    assert cfg.classify_occupancy(149) == CrowdDensityLevel.MODERATE
    assert cfg.classify_occupancy(150) == CrowdDensityLevel.MODERATE
    assert cfg.classify_occupancy(151) == CrowdDensityLevel.HIGH

    # HIGH / CRITICAL boundary
    assert cfg.classify_occupancy(299) == CrowdDensityLevel.HIGH
    assert cfg.classify_occupancy(300) == CrowdDensityLevel.HIGH
    assert cfg.classify_occupancy(301) == CrowdDensityLevel.CRITICAL
    assert cfg.classify_occupancy(500) == CrowdDensityLevel.CRITICAL


def test_venue_specific_thresholds():
    # Small venue: low=10, moderate=20, high=30, critical=31
    small_cfg = CrowdThresholdConfig(low_max=10, moderate_max=20, high_max=30, critical_min=31)
    density = DensityAnalytics(crowd_config=small_cfg)

    res = density.evaluate(occupancy=25)
    assert res.density_level == CrowdDensityLevel.HIGH


def test_congestion_level_transitions():
    cfg = CrowdThresholdConfig(low_max=50, moderate_max=150, high_max=300, critical_min=301)
    density = DensityAnalytics(crowd_config=cfg)

    # Normal
    res1 = density.evaluate(occupancy=50)
    assert res1.congestion_level == CongestionLevel.NORMAL

    # Building (ratio >= 0.6 -> occupancy >= 180)
    res2 = density.evaluate(occupancy=190)
    assert res2.congestion_level == CongestionLevel.BUILDING

    # Congested (ratio >= 0.85 -> occupancy >= 255)
    res3 = density.evaluate(occupancy=260)
    assert res3.congestion_level == CongestionLevel.CONGESTED

    # Severe (ratio >= 1.0 -> occupancy >= 300)
    res4 = density.evaluate(occupancy=320)
    assert res4.congestion_level == CongestionLevel.SEVERE_CONGESTION

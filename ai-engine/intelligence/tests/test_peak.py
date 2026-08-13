"""
Tests for Peak Analytics (peak tracking, timestamps, tie-breaking behavior).
"""
import pytest
from intelligence.analytics.peak import PeakTracker
from intelligence.config.thresholds import CongestionLevel


def test_peak_occupancy_tracking():
    tracker = PeakTracker(venue_id="venue_01")
    tracker.update_occupancy(10, timestamp="2026-01-01T10:00:00+00:00")
    tracker.update_occupancy(50, timestamp="2026-01-01T10:05:00+00:00")
    tracker.update_occupancy(30, timestamp="2026-01-01T10:10:00+00:00")

    peaks = tracker.get_peaks()
    assert peaks.peak_occupancy == 50
    assert peaks.peak_occupancy_timestamp == "2026-01-01T10:05:00+00:00"


def test_peak_occupancy_tie_breaking_preserves_first_occurrence():
    """Equal peak occupancy value must preserve the timestamp of the first occurrence."""
    tracker = PeakTracker()
    tracker.update_occupancy(100, timestamp="2026-01-01T10:00:00+00:00")
    # Equal value 100 later at 10:15
    updated = tracker.update_occupancy(100, timestamp="2026-01-01T10:15:00+00:00")

    assert not updated  # Return False because it did not strictly exceed current peak
    peaks = tracker.get_peaks()
    assert peaks.peak_occupancy == 100
    assert peaks.peak_occupancy_timestamp == "2026-01-01T10:00:00+00:00"


def test_peak_rates_and_congestion():
    tracker = PeakTracker()
    tracker.update_entry_rate(12.5, timestamp="2026-01-01T10:00:00+00:00")
    tracker.update_exit_rate(8.0, timestamp="2026-01-01T10:00:00+00:00")
    tracker.update_congestion(CongestionLevel.CONGESTED, timestamp="2026-01-01T10:05:00+00:00")

    peaks = tracker.get_peaks()
    assert peaks.peak_entry_rate == 12.5
    assert peaks.peak_exit_rate == 8.0
    assert peaks.peak_congestion_level == CongestionLevel.CONGESTED

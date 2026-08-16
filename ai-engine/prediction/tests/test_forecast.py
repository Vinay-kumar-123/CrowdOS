"""
test_forecast.py — Tests for OccupancyForecaster and FlowForecaster.
"""
import pytest
from prediction.forecast.occupancy_forecast import (
    OccupancyForecaster, ForecastConfidence, ForecastStatus
)
from prediction.forecast.flow_forecast import FlowForecaster


@pytest.fixture
def occ_forecaster():
    return OccupancyForecaster()


@pytest.fixture
def flow_forecaster():
    return FlowForecaster()


# ---------------------------------------------------------------------------
# Occupancy Forecasting Tests
# ---------------------------------------------------------------------------

def test_occupancy_forecast_insufficient_data(occ_forecaster):
    occ_forecaster.add_observation(100.0, 1000.0)
    occ_forecaster.add_observation(110.0, 1030.0)
    # only 2 observations (need at least 5 for forecasting)
    res = occ_forecaster.forecast("s1", "v1", "2026-01-01T12:00:30Z", 110.0, 1000)
    assert len(res.forecasts) == 3
    for f in res.forecasts:
        assert f.confidence == ForecastConfidence.INSUFFICIENT_DATA
        assert f.status == ForecastStatus.INSUFFICIENT_DATA
        assert f.projected_value is None


def test_occupancy_forecast_increasing(occ_forecaster):
    # Add 10 observations with rising occupancy: +10 persons per 30s -> +20 persons/min
    for i in range(10):
        occ_forecaster.add_observation(100.0 + i * 10, 1000.0 + i * 30)
    
    res = occ_forecaster.forecast("s1", "v1", "2026-01-01T12:05:00Z", 190.0, 1000)
    assert len(res.forecasts) == 3
    
    f_5m = next(f for f in res.forecasts if f.horizon_minutes == 5)
    assert f_5m.status == ForecastStatus.OK
    assert f_5m.confidence in (ForecastConfidence.LOW, ForecastConfidence.MEDIUM)
    assert f_5m.projected_value > 190.0
    # Expected approx: 190 + (20 * 5) = 290
    assert f_5m.projected_value == pytest.approx(290.0, abs=5.0)


def test_occupancy_forecast_capacity_exceeded_risk(occ_forecaster):
    # Occupancy starts at 900, capacity is 1000, slope is +20/min
    for i in range(10):
        occ_forecaster.add_observation(800.0 + i * 10, 1000.0 + i * 30)
    
    res = occ_forecaster.forecast("s1", "v1", "2026-01-01T12:05:00Z", 890.0, 1000)
    
    # Horizon 10m: 890 + 20*10 = 1090 > 1000 (capacity)
    f_10m = next(f for f in res.forecasts if f.horizon_minutes == 10)
    assert f_10m.status == ForecastStatus.CAPACITY_EXCEEDED_RISK
    assert f_10m.projected_value > 1000.0  # signal preserved, not silently clipped


def test_occupancy_forecast_negative_clipped(occ_forecaster):
    # Occupancy rapidly decreasing: -20 persons per 30s
    for i in range(10):
        occ_forecaster.add_observation(200.0 - i * 20, 1000.0 + i * 30)
    
    res = occ_forecaster.forecast("s1", "v1", "2026-01-01T12:05:00Z", 20.0, 1000)
    
    f_15m = next(f for f in res.forecasts if f.horizon_minutes == 15)
    assert f_15m.status == ForecastStatus.NEGATIVE_CLIPPED
    assert f_15m.projected_value == 0.0


# ---------------------------------------------------------------------------
# Flow Rate Forecasting Tests
# ---------------------------------------------------------------------------

def test_flow_forecast_insufficient_data(flow_forecaster):
    flow_forecaster.add_observation(10.0, 2.0, 1000.0)
    res = flow_forecaster.forecast("s1", "v1", "2026-01-01T12:00:00Z", 10.0, 2.0)
    for f in res.entry_rate_forecasts:
        assert f.confidence == ForecastConfidence.INSUFFICIENT_DATA
    for f in res.net_flow_forecasts:
        assert f.confidence == ForecastConfidence.INSUFFICIENT_DATA


def test_flow_forecast_signed_net_flow(flow_forecaster):
    # Net flow decreasing further into negative: -1 per 30s -> -2/min
    for i in range(10):
        flow_forecaster.add_observation(10.0, -2.0 - i * 1.0, 1000.0 + i * 30)
    
    res = flow_forecaster.forecast("s1", "v1", "2026-01-01T12:05:00Z", 10.0, -11.0)
    f_5m = next(f for f in res.net_flow_forecasts if f.horizon_minutes == 5)
    assert f_5m.status == ForecastStatus.OK
    assert f_5m.projected_value < -11.0  # negative net flow projected accurately without clipping

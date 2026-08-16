"""
conftest.py — Shared fixtures for Sprint 8 prediction tests.
"""
import pytest
from datetime import datetime, timezone, timedelta
from prediction.engine.prediction_engine import PredictionEngine
from prediction.features.snapshot import PredictionInputSnapshot, GateInputSnapshot
from prediction.config.settings import PredictionSettings
from prediction.config.thresholds import PredictionThresholdsConfig


def make_ts(offset_seconds: int = 0) -> str:
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return (base + timedelta(seconds=offset_seconds)).isoformat()


def make_gate(gate_id: str, entry_rate: float = 5.0, exit_rate: float = 3.0,
              net_flow: float = 2.0, occupancy: int = 50) -> GateInputSnapshot:
    return GateInputSnapshot(
        gate_id=gate_id,
        entry_rate_5m=entry_rate,
        exit_rate_5m=exit_rate,
        net_flow_rate_5m=net_flow,
        entry_rate_1m=entry_rate,
        cumulative_entries=100,
        cumulative_exits=80,
        gate_occupancy=occupancy,
        is_active=True,
    )


def make_snapshot(
    session_id: str = "test-session",
    venue_id: str = "test-venue",
    timestamp: str = None,
    session_status: str = "ACTIVE",
    venue_capacity: int = 1000,
    current_occupancy: int = 300,
    entry_rate_5m: float = 10.0,
    exit_rate_5m: float = 8.0,
    net_flow_rate_5m: float = 2.0,
    density_level: str = "MODERATE",
    congestion_level: str = "NORMAL",
    gate_snapshots: dict = None,
    active_anomalies: list = None,
    average_dwell: float = 600.0,
    p95_dwell: float = 1200.0,
) -> PredictionInputSnapshot:
    return PredictionInputSnapshot(
        session_id=session_id,
        venue_id=venue_id,
        timestamp=timestamp or make_ts(0),
        session_status=session_status,
        venue_capacity=venue_capacity,
        current_occupancy=current_occupancy,
        entry_rate_5m=entry_rate_5m,
        exit_rate_5m=exit_rate_5m,
        net_flow_rate_5m=net_flow_rate_5m,
        entry_rate_1m=entry_rate_5m,
        entry_rate_15m=entry_rate_5m,
        density_level=density_level,
        congestion_level=congestion_level,
        occupancy_ratio=current_occupancy / max(1, venue_capacity),
        gate_snapshots=gate_snapshots or {},
        active_anomalies=active_anomalies or [],
        average_dwell=average_dwell,
        p95_dwell=p95_dwell,
    )


@pytest.fixture
def basic_snapshot():
    return make_snapshot()


@pytest.fixture
def engine():
    e = PredictionEngine(venue_id="test-venue")
    yield e
    e.reset()


@pytest.fixture
def three_gate_snapshot():
    gates = {
        "G1": make_gate("G1", entry_rate=10.0),
        "G2": make_gate("G2", entry_rate=5.0),
        "G3": make_gate("G3", entry_rate=8.0),
    }
    return make_snapshot(gate_snapshots=gates)


@pytest.fixture
def high_risk_snapshot():
    return make_snapshot(
        current_occupancy=900,
        venue_capacity=1000,
        entry_rate_5m=35.0,
        exit_rate_5m=5.0,
        net_flow_rate_5m=30.0,
        density_level="CRITICAL",
        congestion_level="SEVERE_CONGESTION",
        active_anomalies=[
            {"anomaly_type": "ENTRY_SURGE", "severity": "CRITICAL", "gate_id": "G1"},
            {"anomaly_type": "OCCUPANCY_SPIKE", "severity": "HIGH", "gate_id": "G1"},
        ],
    )

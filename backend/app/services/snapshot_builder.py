"""
Snapshot Builder — Sprint 9.

Assembles PredictionInputSnapshot (Sprint 8 DTO) from live Sprint 7 engine state.

This module is the only place in backend/ that knows about the Sprint 8
PredictionInputSnapshot schema. It reads from the intelligence engine's
subsystems and constructs the immutable DTO that PredictionEngine.predict()
consumes.

Architecture Rule:
    backend/services/snapshot_builder.py is the ONLY translation layer.
    API endpoints MUST NOT construct PredictionInputSnapshot directly.
"""
import logging
import sys
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

logger = logging.getLogger("crowdos.snapshot_builder")

# Ensure ai-engine is importable (adapter already does this, but guard here too)
_AI_ENGINE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "ai-engine")
)
if _AI_ENGINE_PATH not in sys.path:
    sys.path.insert(0, _AI_ENGINE_PATH)

if TYPE_CHECKING:
    from app.services.ai_engine_adapter import VenueEngines


def build_snapshot(
    engines: "VenueEngines",
    session_id: str,
    session_status: str = "ACTIVE",
) -> Optional[object]:
    """
    Build a PredictionInputSnapshot from live Sprint 7 engine state.

    Returns:
        PredictionInputSnapshot if AI Engine is available and data is valid.
        None if AI Engine is not available (stub mode).

    Raises:
        ValueError if any extracted value violates PredictionInputSnapshot contracts.
    """
    try:
        from prediction.features.snapshot import PredictionInputSnapshot, GateInputSnapshot
    except ImportError:
        logger.warning("PredictionInputSnapshot not importable — snapshot builder in stub mode")
        return None

    intelligence = engines.intelligence
    venue_id = engines.venue_id
    venue_capacity = engines.venue_capacity
    timestamp = datetime.now(timezone.utc).isoformat()

    # --- Extract Sprint 7 data ---
    try:
        intelligence_state = intelligence.get_current_intelligence()
    except Exception as e:
        logger.error(f"Failed to get current intelligence for venue {venue_id}: {e}")
        return None

    flow_data = intelligence_state.get("flow", {})
    occupancy_data = intelligence_state.get("occupancy", {})
    density_data = intelligence_state.get("density", {})
    dwell_data = intelligence_state.get("dwell", {})

    # Flow metrics
    entry_rate_1m = float(flow_data.get("entry_rate_1m", 0.0))
    entry_rate_5m = float(flow_data.get("entry_rate_5m", 0.0))
    exit_rate_5m = float(flow_data.get("exit_rate_5m", 0.0))
    net_flow_rate_5m = float(flow_data.get("net_flow_rate_5m", 0.0))
    entry_rate_15m = float(flow_data.get("entry_rate_15m", 0.0))

    # Occupancy
    current_occupancy = int(occupancy_data.get("current_occupancy", 0))
    total_entries = int(flow_data.get("cumulative_entries", 0))
    total_exits = int(flow_data.get("cumulative_exits", 0))
    busiest_gate = occupancy_data.get("busiest_gate", None)
    gate_occupancy_raw = occupancy_data.get("gate_occupancy", {})
    gate_occupancy = {k: int(v) for k, v in gate_occupancy_raw.items()}

    # Density
    density_level = str(density_data.get("density_level", "LOW"))
    congestion_level = str(density_data.get("congestion_level", "NORMAL"))
    occupancy_ratio = float(density_data.get("occupancy_ratio", 0.0))

    # Dwell
    average_dwell = float(dwell_data.get("average_dwell", 0.0))
    p95_dwell = float(dwell_data.get("p95_dwell", 0.0))

    # Alerts count
    active_alert_count = int(intelligence_state.get("active_alerts_count", 0))

    # Active anomalies — extract type + severity + gate_id only (privacy-safe)
    active_anomalies = []
    try:
        raw_alerts = intelligence.alert_manager.get_active_alerts()
        for alert in raw_alerts:
            anomaly_entry = {
                "anomaly_type": getattr(alert, "type", "UNKNOWN"),
                "severity": str(getattr(alert, "severity", "MEDIUM")),
                "gate_id": getattr(alert, "gate_id", None) or "",
            }
            active_anomalies.append(anomaly_entry)
    except Exception as e:
        logger.debug(f"Could not extract active anomalies: {e}")
        active_anomalies = []

    # Gate-level snapshots from flow analytics
    gate_snapshots = {}
    try:
        gate_flows = intelligence.flow_analytics.get_all_gate_flows() if intelligence.flow_analytics else {}
        for gate_id, gate_flow in gate_flows.items():
            gate_occ = gate_occupancy.get(gate_id, 0)
            gate_snapshots[gate_id] = GateInputSnapshot(
                gate_id=gate_id,
                entry_rate_5m=float(gate_flow.entry_rate_5m),
                exit_rate_5m=float(gate_flow.exit_rate_5m),
                net_flow_rate_5m=float(gate_flow.net_flow_rate_5m),
                entry_rate_1m=float(gate_flow.entry_rate_1m),
                cumulative_entries=int(gate_flow.cumulative_entries),
                cumulative_exits=int(gate_flow.cumulative_exits),
                gate_occupancy=gate_occ,
                is_active=True,
            )
    except Exception as e:
        logger.debug(f"Could not build gate snapshots: {e}")
        gate_snapshots = {}

    # Clamp negatives that can arise from stale/zero state to safe values
    # NOTE: PredictionInputSnapshot raises ValueError for negative rates,
    # but entry/exit rates from FlowMetrics are always >= 0 by design.
    # net_flow_rate_5m is signed and allowed to be negative.

    try:
        snapshot = PredictionInputSnapshot(
            session_id=session_id,
            venue_id=venue_id,
            timestamp=timestamp,
            session_status=session_status,
            venue_capacity=venue_capacity,
            current_occupancy=current_occupancy,
            total_entries=total_entries,
            total_exits=total_exits,
            busiest_gate=busiest_gate,
            gate_occupancy=gate_occupancy,
            entry_rate_1m=entry_rate_1m,
            entry_rate_5m=entry_rate_5m,
            exit_rate_5m=exit_rate_5m,
            net_flow_rate_5m=net_flow_rate_5m,
            entry_rate_15m=entry_rate_15m,
            density_level=density_level,
            congestion_level=congestion_level,
            occupancy_ratio=occupancy_ratio,
            gate_snapshots=gate_snapshots,
            active_anomalies=active_anomalies,
            active_alert_count=active_alert_count,
            average_dwell=average_dwell,
            p95_dwell=p95_dwell,
        )
        return snapshot
    except ValueError as ve:
        logger.error(f"Invalid snapshot data for venue {venue_id}: {ve}")
        raise

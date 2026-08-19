"""
Intelligence Service — Sprint 9.

Retrieves Sprint 7 intelligence state from the live EventIntelligenceEngine
and maps it into Sprint 9 API response schemas.

Architecture:
    - Reads from engine.get_current_intelligence() and sub-components.
    - NO business logic is duplicated here.
    - ALL intelligence computations live in Sprint 7 ai-engine/intelligence/.
    - Privacy: NO biometric fields in any returned schema.
"""
import logging
from typing import List, Optional
from app.services.ai_engine_adapter import VenueEngineRegistry, VenueEngines
from app.schemas.intelligence import (
    FlowMetricsResponse,
    OccupancySummaryResponse,
    DensityStateResponse,
    DwellMetricsResponse,
    AlertResponse,
    AlertListResponse,
    CurrentIntelligenceResponse,
)
from app.core.exceptions import NotFoundException

logger = logging.getLogger("crowdos.intelligence_service")


class IntelligenceService:
    """
    Read-only service for Sprint 7 intelligence queries.
    """

    def __init__(self, registry: VenueEngineRegistry):
        self._registry = registry

    def _get_engines(self, venue_id: str) -> VenueEngines:
        engines = self._registry.get(venue_id)
        if engines is None:
            raise NotFoundException(f"Venue '{venue_id}' not initialized.")
        return engines

    # ------------------------------------------------------------------
    # Current intelligence snapshot
    # ------------------------------------------------------------------

    def get_current_intelligence(self, venue_id: str) -> CurrentIntelligenceResponse:
        """Returns complete current intelligence state for the venue."""
        engines = self._get_engines(venue_id)
        state = engines.intelligence.get_current_intelligence()

        flow_data = state.get("flow", {})
        occ_data = state.get("occupancy", {})
        density_data = state.get("density", {})
        dwell_data = state.get("dwell", {})

        # Active session id
        active_session = engines.intelligence.session_manager.get_active_session()
        active_session_id = active_session.session_id if active_session else None

        flow = FlowMetricsResponse(
            venue_id=venue_id,
            gate_id=None,
            cumulative_entries=flow_data.get("cumulative_entries", 0),
            cumulative_exits=flow_data.get("cumulative_exits", 0),
            cumulative_net_flow=flow_data.get("cumulative_net_flow", 0),
            entry_rate_1m=flow_data.get("entry_rate_1m", 0.0),
            exit_rate_1m=flow_data.get("exit_rate_1m", 0.0),
            net_flow_rate_1m=flow_data.get("net_flow_rate_1m", 0.0),
            entry_rate_5m=flow_data.get("entry_rate_5m", 0.0),
            exit_rate_5m=flow_data.get("exit_rate_5m", 0.0),
            net_flow_rate_5m=flow_data.get("net_flow_rate_5m", 0.0),
            entry_rate_15m=flow_data.get("entry_rate_15m", 0.0),
            exit_rate_15m=flow_data.get("exit_rate_15m", 0.0),
            net_flow_rate_15m=flow_data.get("net_flow_rate_15m", 0.0),
            entry_rate_60m=flow_data.get("entry_rate_60m", 0.0),
            exit_rate_60m=flow_data.get("exit_rate_60m", 0.0),
            net_flow_rate_60m=flow_data.get("net_flow_rate_60m", 0.0),
        )

        occupancy = OccupancySummaryResponse(
            venue_id=occ_data.get("venue_id", venue_id),
            current_occupancy=occ_data.get("current_occupancy", 0),
            total_entries=occ_data.get("total_entries", 0),
            total_exits=occ_data.get("total_exits", 0),
            gate_occupancy=occ_data.get("gate_occupancy", {}),
            busiest_gate=occ_data.get("busiest_gate"),
            least_active_gate=occ_data.get("least_active_gate"),
            last_updated=occ_data.get("last_updated", ""),
        )

        density = DensityStateResponse(
            venue_id=density_data.get("venue_id", venue_id),
            occupancy=density_data.get("occupancy", 0),
            density_level=density_data.get("density_level", "LOW"),
            congestion_level=density_data.get("congestion_level", "NORMAL"),
            occupancy_ratio=density_data.get("occupancy_ratio", 0.0),
        )

        dwell = DwellMetricsResponse(
            venue_id=venue_id,
            average_dwell=dwell_data.get("average_dwell", 0.0),
            median_dwell=dwell_data.get("median_dwell", 0.0),
            p95_dwell=dwell_data.get("p95_dwell", 0.0),
            sample_count=dwell_data.get("count", 0),
        )

        return CurrentIntelligenceResponse(
            venue_id=venue_id,
            flow=flow,
            occupancy=occupancy,
            density=density,
            dwell=dwell,
            active_alerts_count=state.get("active_alerts_count", 0),
            active_session_id=active_session_id,
        )

    # ------------------------------------------------------------------
    # Flow analytics
    # ------------------------------------------------------------------

    def get_venue_flow(self, venue_id: str) -> FlowMetricsResponse:
        engines = self._get_engines(venue_id)
        try:
            flow = engines.intelligence.flow_analytics.get_venue_flow()
            d = flow.to_dict() if hasattr(flow, "to_dict") else dict(flow)
        except Exception:
            d = {}
        return FlowMetricsResponse(venue_id=venue_id, **_extract_flow_fields(d))

    def get_gate_flow(self, venue_id: str, gate_id: str) -> FlowMetricsResponse:
        engines = self._get_engines(venue_id)
        try:
            flow = engines.intelligence.flow_analytics.get_gate_flow(gate_id)
            d = flow.to_dict() if hasattr(flow, "to_dict") else dict(flow)
        except Exception:
            d = {}
        return FlowMetricsResponse(venue_id=venue_id, gate_id=gate_id, **_extract_flow_fields(d))

    def get_all_gate_flows(self, venue_id: str):
        engines = self._get_engines(venue_id)
        try:
            gate_flows = engines.intelligence.flow_analytics.get_all_gate_flows()
            result = {}
            for gid, gf in gate_flows.items():
                d = gf.to_dict() if hasattr(gf, "to_dict") else {}
                result[gid] = FlowMetricsResponse(venue_id=venue_id, gate_id=gid, **_extract_flow_fields(d))
            return result
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Occupancy analytics
    # ------------------------------------------------------------------

    def get_occupancy_summary(self, venue_id: str) -> OccupancySummaryResponse:
        engines = self._get_engines(venue_id)
        try:
            summary = engines.intelligence.occupancy_analytics.get_summary()
            d = summary.to_dict() if hasattr(summary, "to_dict") else {}
        except Exception:
            d = {}
        return OccupancySummaryResponse(
            venue_id=venue_id,
            current_occupancy=d.get("current_occupancy", 0),
            total_entries=d.get("total_entries", 0),
            total_exits=d.get("total_exits", 0),
            gate_occupancy=d.get("gate_occupancy", {}),
            busiest_gate=d.get("busiest_gate"),
            least_active_gate=d.get("least_active_gate"),
            last_updated=d.get("last_updated", ""),
        )

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def get_active_alerts(self, venue_id: str) -> AlertListResponse:
        engines = self._get_engines(venue_id)
        active = engines.intelligence.alert_manager.get_active_alerts()
        items = [_map_alert(a) for a in active]
        return AlertListResponse(
            venue_id=venue_id,
            alerts=items,
            total=len(items),
            active_count=len(items),
        )

    def get_all_alerts(self, venue_id: str) -> AlertListResponse:
        engines = self._get_engines(venue_id)
        all_alerts = engines.intelligence.alert_manager.get_all_alerts()
        active_alerts = engines.intelligence.alert_manager.get_active_alerts()
        items = [_map_alert(a) for a in all_alerts]
        return AlertListResponse(
            venue_id=venue_id,
            alerts=items,
            total=len(items),
            active_count=len(active_alerts),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_flow_fields(d: dict) -> dict:
    keys = [
        "cumulative_entries", "cumulative_exits", "cumulative_net_flow",
        "entry_rate_1m", "exit_rate_1m", "net_flow_rate_1m",
        "entry_rate_5m", "exit_rate_5m", "net_flow_rate_5m",
        "entry_rate_15m", "exit_rate_15m", "net_flow_rate_15m",
        "entry_rate_60m", "exit_rate_60m", "net_flow_rate_60m",
    ]
    return {k: d.get(k, 0.0 if "rate" in k or "net" in k else 0) for k in keys}


def _map_alert(alert) -> AlertResponse:
    if hasattr(alert, "to_dict"):
        d = alert.to_dict()
    else:
        d = {}
    return AlertResponse(
        alert_id=d.get("alert_id", ""),
        session_id=d.get("session_id", ""),
        venue_id=d.get("venue_id", ""),
        gate_id=d.get("gate_id"),
        type=d.get("type", ""),
        severity=d.get("severity", "MEDIUM"),
        status=d.get("status", "ACTIVE"),
        created_at=d.get("created_at", ""),
        last_seen=d.get("last_seen", ""),
        resolved_at=d.get("resolved_at"),
    )

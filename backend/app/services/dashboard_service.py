"""
Dashboard Service — Sprint 9.

Aggregates existing Sprint 6, 7, and 8 intelligence outputs into a unified
real-time dashboard snapshot.
Zero duplicate business calculations — delegates strictly to live engines.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from app.services.ai_engine_adapter import VenueEngineRegistry, VenueEngines
from app.services.snapshot_builder import build_snapshot
from app.schemas.dashboard import DashboardSnapshotResponse
from app.core.exceptions import NotFoundException

logger = logging.getLogger("crowdos.dashboard_service")


class DashboardService:
    """
    Service aggregating unified dashboard snapshot from live Sprint 6, 7, and 8 engines.
    """

    def __init__(self, registry: VenueEngineRegistry):
        self._registry = registry

    def get_dashboard_by_session_id(self, session_id: str) -> DashboardSnapshotResponse:
        """
        Look up session across all venues and generate its unified dashboard snapshot.
        """
        match = self._registry.find_venue_by_session(session_id)
        if match is None:
            raise NotFoundException(f"Session '{session_id}' not found in any registered venue.")

        venue_id, engines = match
        return self._build_dashboard_snapshot(venue_id, session_id, engines)

    def get_dashboard_for_venue_session(
        self, venue_id: str, session_id: str
    ) -> DashboardSnapshotResponse:
        """
        Generate unified dashboard snapshot for a specific venue and session ID.
        """
        engines = self._registry.get(venue_id)
        if engines is None:
            raise NotFoundException(f"Venue '{venue_id}' not found.")

        session = engines.intelligence.session_manager.get_session(session_id)
        if session is None:
            raise NotFoundException(f"Session '{session_id}' not found for venue '{venue_id}'.")

        return self._build_dashboard_snapshot(venue_id, session_id, engines)

    def _build_dashboard_snapshot(
        self, venue_id: str, session_id: str, engines: VenueEngines
    ) -> DashboardSnapshotResponse:
        session = engines.intelligence.session_manager.get_session(session_id)
        session_status = getattr(session, "status", "UNKNOWN")
        if hasattr(session_status, "value"):
            session_status_str = session_status.value
        else:
            session_status_str = str(session_status)

        timestamp = datetime.now(timezone.utc).isoformat()
        venue_capacity = engines.venue_capacity

        # 1. Sprint 7 Intelligence State
        intel_state = engines.intelligence.get_current_intelligence()
        flow_data = intel_state.get("flow", {})
        occ_data = intel_state.get("occupancy", {})
        density_data = intel_state.get("density", {})

        current_occupancy = int(occ_data.get("current_occupancy", 0))
        total_entries = int(flow_data.get("cumulative_entries", 0))
        total_exits = int(flow_data.get("cumulative_exits", 0))
        net_flow = int(flow_data.get("cumulative_net_flow", total_entries - total_exits))

        entry_rate_5m = float(flow_data.get("entry_rate_5m", 0.0))
        exit_rate_5m = float(flow_data.get("exit_rate_5m", 0.0))
        net_flow_rate_5m = float(flow_data.get("net_flow_rate_5m", 0.0))

        density_level = str(density_data.get("density_level", "LOW"))
        congestion_level = str(density_data.get("congestion_level", "NORMAL"))
        occupancy_ratio = float(density_data.get("occupancy_ratio", 0.0))

        # 2. Alerts & Anomalies
        active_alerts_raw = engines.intelligence.alert_manager.get_active_alerts()
        active_alerts = []
        active_anomalies = []
        for a in active_alerts_raw:
            a_dict = a.to_dict() if hasattr(a, "to_dict") else {}
            active_alerts.append(a_dict)
            active_anomalies.append({
                "type": a_dict.get("type", ""),
                "severity": a_dict.get("severity", "MEDIUM"),
                "gate_id": a_dict.get("gate_id"),
            })

        # 3. Gate Summaries from Flow Analytics
        gate_summaries = {}
        if engines.intelligence.flow_analytics:
            gate_flows = engines.intelligence.flow_analytics.get_all_gate_flows()
            gate_occs = occ_data.get("gate_occupancy", {})
            for gid, gf in gate_flows.items():
                gf_dict = gf.to_dict() if hasattr(gf, "to_dict") else {}
                gate_summaries[gid] = {
                    "gate_id": gid,
                    "occupancy": gate_occs.get(gid, 0),
                    "entry_rate_5m": gf_dict.get("entry_rate_5m", 0.0),
                    "exit_rate_5m": gf_dict.get("exit_rate_5m", 0.0),
                    "net_flow_rate_5m": gf_dict.get("net_flow_rate_5m", 0.0),
                    "cumulative_entries": gf_dict.get("cumulative_entries", 0),
                    "cumulative_exits": gf_dict.get("cumulative_exits", 0),
                }

        # 4. Sprint 8 Predictions (if session is active or created)
        risk_level = "LOW"
        risk_score = 0.0
        risk_factors: List[Dict[str, Any]] = []
        trend_direction = "STABLE"
        trend_slope = None
        occ_forecast = None
        flow_forecast = None
        primary_recommendation = "MONITOR"
        recommendations = ["MONITOR"]

        if session_status_str in ("ACTIVE", "CREATED", "PAUSED"):
            try:
                snapshot = build_snapshot(engines, session_id, session_status_str)
                if snapshot and hasattr(engines.prediction, "predict"):
                    pred_res = engines.prediction.predict(snapshot)
                    pred_dict = pred_res.to_dict() if hasattr(pred_res, "to_dict") else {}

                    if pred_dict.get("venue_risk"):
                        vr = pred_dict["venue_risk"]
                        risk_level = vr.get("risk_level", "LOW")
                        risk_score = vr.get("score", 0.0)
                        risk_factors = vr.get("factors", [])

                    if pred_dict.get("venue_trend"):
                        vt = pred_dict["venue_trend"]
                        trend_direction = vt.get("direction", "STABLE")
                        trend_slope = vt.get("slope")

                    if pred_dict.get("occupancy_forecast"):
                        occ_forecast = pred_dict["occupancy_forecast"]

                    if pred_dict.get("flow_forecast"):
                        flow_forecast = pred_dict["flow_forecast"]

                    if pred_dict.get("venue_decision"):
                        vd = pred_dict["venue_decision"]
                        primary_recommendation = vd.get("action", "MONITOR")
                        recs = [primary_recommendation]
                        for sec in vd.get("secondary_reasons", []):
                            if sec and sec not in recs:
                                recs.append(sec)
                        recommendations = recs
            except Exception as pred_err:
                logger.debug(f"Dashboard prediction evaluation skipped: {pred_err}")

        return DashboardSnapshotResponse(
            session_id=session_id,
            venue_id=venue_id,
            session_status=session_status_str,
            venue_capacity=venue_capacity,
            current_occupancy=current_occupancy,
            occupancy_ratio=round(occupancy_ratio, 4),
            total_entries=total_entries,
            total_exits=total_exits,
            net_flow=net_flow,
            entry_rate_5m=round(entry_rate_5m, 2),
            exit_rate_5m=round(exit_rate_5m, 2),
            net_flow_rate_5m=round(net_flow_rate_5m, 2),
            density_level=density_level,
            congestion_level=congestion_level,
            active_alerts_count=len(active_alerts),
            active_alerts=active_alerts,
            active_anomalies=active_anomalies,
            risk_level=risk_level,
            risk_score=risk_score,
            risk_factors=risk_factors,
            trend_direction=trend_direction,
            trend_slope=trend_slope,
            occupancy_forecast=occ_forecast,
            flow_forecast=flow_forecast,
            primary_recommendation=primary_recommendation,
            recommendations=recommendations,
            gate_summaries=gate_summaries,
            timestamp=timestamp,
        )

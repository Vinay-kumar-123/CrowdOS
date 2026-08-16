"""
PredictionEngine — Top-level Sprint 8 Orchestrator.

Consumes PredictionInputSnapshot (built from Sprint 7 outputs).
Produces PredictionResult containing:
  - FeatureVector
  - RiskResult (with hysteresis)
  - TrendResult
  - OccupancyForecastResult
  - FlowForecastResult
  - DecisionResult
  - Gate-level prediction results

Thread-safe via threading.Lock on shared mutable state.

Session safety:
  STOPPED / EXPIRED → status="skipped" (no predictions produced)
  PAUSED            → status="paused"
  CREATED / ACTIVE  → normal prediction

Idempotency:
  Key: session_id + venue_id + timestamp
  Duplicate (same key within window) → status="duplicate"

Hysteresis:
  Escalation: escalation_persistence_frames consecutive crossings required
  Recovery:   recovery_persistence_frames consecutive crossings required
  One gate's state NEVER contaminates another gate's state.
"""
import time
import threading
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field

from prediction.features.snapshot import PredictionInputSnapshot, GateInputSnapshot
from prediction.features.feature_extractor import FeatureExtractor
from prediction.risk.risk_score import RiskResult, RiskScorer
from prediction.risk.risk_level import RiskLevel, RISK_LEVEL_ORDER
from prediction.trend.trend_state import TrendResult, TrendDirection
from prediction.trend.trend_detector import TrendDetector
from prediction.forecast.occupancy_forecast import OccupancyForecastResult, OccupancyForecaster
from prediction.forecast.flow_forecast import FlowForecastResult, FlowForecaster
from prediction.decision.decision_schema import DecisionResult, DecisionAction
from prediction.decision.decision_engine import DecisionEngine
from prediction.metrics.metrics import PredictionMetricsTracker
from prediction.config.settings import PredictionSettings, default_prediction_settings
from prediction.config.thresholds import PredictionThresholdsConfig, default_thresholds
from prediction.utils.logger import prediction_logger


TERMINAL_SESSION_STATES = {"STOPPED", "EXPIRED"}
PAUSED_SESSION_STATES = {"PAUSED"}


class GatePredictionResult(BaseModel):
    gate_id: str
    risk_result: RiskResult
    trend_result: TrendResult
    decision_result: DecisionResult

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "risk": self.risk_result.to_dict(),
            "trend": self.trend_result.to_dict(),
            "decision": self.decision_result.to_dict(),
        }


class PredictionResult(BaseModel):
    session_id: str
    venue_id: str
    timestamp: str
    status: str = Field(default="ok")
    message: str = Field(default="")
    venue_risk: Optional[RiskResult] = None
    venue_trend: Optional[TrendResult] = None
    venue_decision: Optional[DecisionResult] = None
    occupancy_forecast: Optional[OccupancyForecastResult] = None
    flow_forecast: Optional[FlowForecastResult] = None
    gate_results: Dict[str, Any] = Field(default_factory=dict)
    processing_time_ms: float = Field(default=0.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "venue_id": self.venue_id,
            "timestamp": self.timestamp,
            "status": self.status,
            "message": self.message,
            "venue_risk": self.venue_risk.to_dict() if self.venue_risk else None,
            "venue_trend": self.venue_trend.to_dict() if self.venue_trend else None,
            "venue_decision": self.venue_decision.to_dict() if self.venue_decision else None,
            "occupancy_forecast": self.occupancy_forecast.to_dict() if self.occupancy_forecast else None,
            "flow_forecast": self.flow_forecast.to_dict() if self.flow_forecast else None,
            "gate_results": self.gate_results,
            "processing_time_ms": round(self.processing_time_ms, 3),
        }


class _GateState:
    """Per-gate independent state. Never shared across gates."""

    def __init__(self, settings: PredictionSettings, thresholds: PredictionThresholdsConfig):
        self.trend_detector = TrendDetector(settings=settings, thresholds=thresholds.trend)
        self.current_risk_level: RiskLevel = RiskLevel.LOW
        self.escalation_count: int = 0
        self.recovery_count: int = 0


class PredictionEngine:
    """
    Top-level Sprint 8 Prediction Engine Orchestrator.
    One instance per venue. Thread-safe.
    """

    def __init__(
        self,
        venue_id: str = "default_venue",
        settings: Optional[PredictionSettings] = None,
        config: Optional[PredictionThresholdsConfig] = None,
    ):
        self.venue_id = venue_id
        self.settings = settings or default_prediction_settings
        self.config = config or default_thresholds

        self._lock = threading.Lock()

        # Stateless components (safe to share)
        self.extractor = FeatureExtractor(thresholds=self.config.features)
        self.scorer = RiskScorer(config=self.config)
        self.decision_engine = DecisionEngine(config=self.config)
        self.metrics = PredictionMetricsTracker()

        # Venue-level stateful components
        self._venue_trend_detector = TrendDetector(
            settings=self.settings, thresholds=self.config.trend
        )
        self._occupancy_forecaster = OccupancyForecaster(settings=self.settings)
        self._flow_forecaster = FlowForecaster(settings=self.settings)

        # Hysteresis state (venue-level)
        self._current_risk_level: RiskLevel = RiskLevel.LOW
        self._escalation_count: int = 0
        self._recovery_count: int = 0

        # Gate-level state: gate_id -> _GateState
        self._gate_states: Dict[str, _GateState] = {}

        # Idempotency: "session_id:venue_id" -> last processed timestamp
        self._last_processed: Dict[str, str] = {}

    # -----------------------------------------------------------------------
    # Main prediction entrypoint
    # -----------------------------------------------------------------------

    def predict(self, snapshot: PredictionInputSnapshot) -> PredictionResult:
        """
        Process one PredictionInputSnapshot and return PredictionResult.
        Thread-safe. Idempotent for duplicate timestamps.
        """
        t0 = time.perf_counter()

        # Session safety
        if snapshot.session_status in TERMINAL_SESSION_STATES:
            self.metrics.record_session_skipped()
            return PredictionResult(
                session_id=snapshot.session_id,
                venue_id=snapshot.venue_id,
                timestamp=snapshot.timestamp,
                status="skipped",
                message=f"Session is {snapshot.session_status} — no active predictions produced.",
                processing_time_ms=0.0,
            )

        if snapshot.session_status in PAUSED_SESSION_STATES:
            return PredictionResult(
                session_id=snapshot.session_id,
                venue_id=snapshot.venue_id,
                timestamp=snapshot.timestamp,
                status="paused",
                message="Session is PAUSED — prediction suspended.",
                processing_time_ms=0.0,
            )

        # Idempotency
        ikey = f"{snapshot.session_id}:{snapshot.venue_id}"
        with self._lock:
            if self._last_processed.get(ikey) == snapshot.timestamp:
                self.metrics.record_duplicate_rejected()
                return PredictionResult(
                    session_id=snapshot.session_id,
                    venue_id=snapshot.venue_id,
                    timestamp=snapshot.timestamp,
                    status="duplicate",
                    message="Duplicate snapshot (same session + timestamp) — rejected.",
                    processing_time_ms=0.0,
                )
            self._last_processed[ikey] = snapshot.timestamp

        try:
            # Parse timestamp to epoch for time-series operations
            epoch_ts = self._parse_epoch(snapshot.timestamp)

            # 1. Feature extraction
            fv = self.extractor.extract(snapshot)

            # 2. Risk scoring
            raw_risk = self.scorer.score(fv)

            # 3. Hysteresis (venue-level)
            with self._lock:
                stabilized_risk = self._apply_hysteresis_unlocked(raw_risk)

            # 4. Update time-series histories
            self._venue_trend_detector.add_observation(stabilized_risk.score, epoch_ts)
            self._occupancy_forecaster.add_observation(float(snapshot.current_occupancy), epoch_ts)
            self._flow_forecaster.add_observation(
                snapshot.entry_rate_5m, snapshot.net_flow_rate_5m, epoch_ts
            )

            # 5. Trend detection
            trend = self._venue_trend_detector.detect(
                snapshot.session_id, snapshot.venue_id, snapshot.timestamp
            )

            # 6. Forecasting
            occ_forecast = self._occupancy_forecaster.forecast(
                snapshot.session_id, snapshot.venue_id, snapshot.timestamp,
                float(snapshot.current_occupancy), snapshot.venue_capacity,
            )
            flow_forecast = self._flow_forecaster.forecast(
                snapshot.session_id, snapshot.venue_id, snapshot.timestamp,
                snapshot.entry_rate_5m, snapshot.net_flow_rate_5m,
            )

            # 7. Decision (venue-level)
            decision = self.decision_engine.decide(stabilized_risk, trend, occ_forecast)

            # 8. Gate-level predictions (each gate fully independent)
            gate_results = {}
            for gate_id, gate_snap in snapshot.gate_snapshots.items():
                try:
                    gate_pred = self._predict_gate(gate_id, gate_snap, snapshot, epoch_ts)
                    gate_results[gate_id] = gate_pred.to_dict()
                except Exception as gate_err:
                    prediction_logger.error(
                        f"Gate prediction error for {gate_id}: {gate_err}"
                    )
                    gate_results[gate_id] = {"error": str(gate_err)}

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self.metrics.record_prediction(
                risk_level_str=stabilized_risk.risk_level.value,
                latency_ms=elapsed_ms,
                insufficient_data=not stabilized_risk.data_sufficient,
            )

            return PredictionResult(
                session_id=snapshot.session_id,
                venue_id=snapshot.venue_id,
                timestamp=snapshot.timestamp,
                status="ok",
                venue_risk=stabilized_risk,
                venue_trend=trend,
                venue_decision=decision,
                occupancy_forecast=occ_forecast,
                flow_forecast=flow_forecast,
                gate_results=gate_results,
                processing_time_ms=round(elapsed_ms, 3),
            )

        except Exception as e:
            self.metrics.record_error()
            prediction_logger.error(f"PredictionEngine.predict() error: {e}")
            return PredictionResult(
                session_id=snapshot.session_id,
                venue_id=snapshot.venue_id,
                timestamp=snapshot.timestamp,
                status="error",
                message=str(e),
                processing_time_ms=(time.perf_counter() - t0) * 1000.0,
            )

    # -----------------------------------------------------------------------
    # Gate-level prediction (fully isolated per gate)
    # -----------------------------------------------------------------------

    def _predict_gate(
        self,
        gate_id: str,
        gate_snap: GateInputSnapshot,
        parent: PredictionInputSnapshot,
        epoch_ts: float,
    ) -> GatePredictionResult:
        """
        Produce independent risk/trend/decision for a single gate.
        Uses a gate-scoped mini-snapshot. Gate state is fully isolated.
        """
        gate_snapshot = PredictionInputSnapshot(
            session_id=parent.session_id,
            venue_id=parent.venue_id,
            timestamp=parent.timestamp,
            session_status=parent.session_status,
            venue_capacity=parent.venue_capacity,
            current_occupancy=gate_snap.gate_occupancy,
            total_entries=gate_snap.cumulative_entries,
            total_exits=gate_snap.cumulative_exits,
            busiest_gate=gate_id,
            gate_occupancy={gate_id: gate_snap.gate_occupancy},
            entry_rate_1m=gate_snap.entry_rate_1m,
            entry_rate_5m=gate_snap.entry_rate_5m,
            exit_rate_5m=gate_snap.exit_rate_5m,
            net_flow_rate_5m=gate_snap.net_flow_rate_5m,
            entry_rate_15m=gate_snap.entry_rate_1m,
            density_level=parent.density_level,
            congestion_level=parent.congestion_level,
            occupancy_ratio=parent.occupancy_ratio,
            gate_snapshots={gate_id: gate_snap},
            active_anomalies=[
                a for a in parent.active_anomalies
                if a.get("gate_id") == gate_id
            ],
            active_alert_count=0,
            average_dwell=parent.average_dwell,
            p95_dwell=parent.p95_dwell,
        )

        gate_fv = self.extractor.extract(gate_snapshot)
        gate_risk = self.scorer.score(gate_fv)

        # Get or create gate-specific state
        with self._lock:
            if gate_id not in self._gate_states:
                self._gate_states[gate_id] = _GateState(self.settings, self.config)
            gs = self._gate_states[gate_id]

        # Apply gate-level hysteresis
        with self._lock:
            gate_risk_stabilized = self._apply_hysteresis_for_gate_unlocked(gs, gate_risk)

        gs.trend_detector.add_observation(gate_risk_stabilized.score, epoch_ts)
        gate_trend = gs.trend_detector.detect(
            parent.session_id, parent.venue_id, parent.timestamp
        )
        gate_decision = self.decision_engine.decide(
            gate_risk_stabilized, gate_trend, None, gate_id=gate_id
        )

        return GatePredictionResult(
            gate_id=gate_id,
            risk_result=gate_risk_stabilized,
            trend_result=gate_trend,
            decision_result=gate_decision,
        )

    # -----------------------------------------------------------------------
    # Hysteresis
    # -----------------------------------------------------------------------

    def _apply_hysteresis_unlocked(self, raw_risk: RiskResult) -> RiskResult:
        """Apply venue-level persistence/hysteresis. Must be called under self._lock."""
        return self._apply_hysteresis_state(
            raw_risk,
            self,
            "_current_risk_level",
            "_escalation_count",
            "_recovery_count",
        )

    def _apply_hysteresis_for_gate_unlocked(
        self, gs: _GateState, raw_risk: RiskResult
    ) -> RiskResult:
        """Apply gate-level hysteresis using gate's own state."""
        new_level = raw_risk.risk_level
        current = gs.current_risk_level
        new_order = RISK_LEVEL_ORDER.get(new_level, 0)
        current_order = RISK_LEVEL_ORDER.get(current, 0)

        if new_order > current_order:
            gs.escalation_count += 1
            gs.recovery_count = 0
            if gs.escalation_count >= self.settings.escalation_persistence_frames:
                gs.current_risk_level = new_level
                gs.escalation_count = 0
        elif new_order < current_order:
            gs.recovery_count += 1
            gs.escalation_count = 0
            if gs.recovery_count >= self.settings.recovery_persistence_frames:
                gs.current_risk_level = new_level
                gs.recovery_count = 0
        else:
            gs.escalation_count = 0
            gs.recovery_count = 0

        if gs.current_risk_level != raw_risk.risk_level:
            return raw_risk.model_copy(update={"risk_level": gs.current_risk_level})
        return raw_risk

    def _apply_hysteresis_state(
        self, raw_risk: RiskResult, obj, level_attr, esc_attr, rec_attr
    ) -> RiskResult:
        """Generic hysteresis logic on arbitrary object attributes."""
        new_level = raw_risk.risk_level
        current = getattr(obj, level_attr)
        new_order = RISK_LEVEL_ORDER.get(new_level, 0)
        current_order = RISK_LEVEL_ORDER.get(current, 0)

        if new_order > current_order:
            setattr(obj, esc_attr, getattr(obj, esc_attr) + 1)
            setattr(obj, rec_attr, 0)
            if getattr(obj, esc_attr) >= self.settings.escalation_persistence_frames:
                setattr(obj, level_attr, new_level)
                setattr(obj, esc_attr, 0)
        elif new_order < current_order:
            setattr(obj, rec_attr, getattr(obj, rec_attr) + 1)
            setattr(obj, esc_attr, 0)
            if getattr(obj, rec_attr) >= self.settings.recovery_persistence_frames:
                setattr(obj, level_attr, new_level)
                setattr(obj, rec_attr, 0)
        else:
            setattr(obj, esc_attr, 0)
            setattr(obj, rec_attr, 0)

        current_after = getattr(obj, level_attr)
        if current_after != raw_risk.risk_level:
            return raw_risk.model_copy(update={"risk_level": current_after})
        return raw_risk

    # -----------------------------------------------------------------------
    # Utilities
    # -----------------------------------------------------------------------

    @staticmethod
    def _parse_epoch(timestamp: str) -> float:
        from datetime import datetime
        try:
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
        except Exception:
            return time.time()

    def get_metrics(self) -> Dict[str, Any]:
        return self.metrics.get_metrics()

    def reset(self) -> None:
        """Reset all engine state."""
        with self._lock:
            self._venue_trend_detector.reset()
            self._occupancy_forecaster.reset()
            self._flow_forecaster.reset()
            for gs in self._gate_states.values():
                gs.trend_detector.reset()
                gs.current_risk_level = RiskLevel.LOW
                gs.escalation_count = 0
                gs.recovery_count = 0
            self._gate_states.clear()
            self._current_risk_level = RiskLevel.LOW
            self._escalation_count = 0
            self._recovery_count = 0
            self._last_processed.clear()
            self.metrics.reset()

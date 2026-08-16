"""
PredictionMetricsTracker — Thread-safe atomic counters for Sprint 8.
"""
import time
import threading
from typing import Dict, Any


class PredictionMetricsTracker:
    """Thread-safe metrics tracker for Prediction Engine operations."""

    def __init__(self):
        self._lock = threading.Lock()
        self._reset_unlocked()

    def _reset_unlocked(self) -> None:
        self.prediction_evaluations = 0
        self.risk_evaluations = 0
        self.decisions_generated = 0
        self.insufficient_data_predictions = 0
        self.forecast_failures = 0
        self.malformed_inputs = 0
        self.high_risk_states = 0
        self.critical_risk_states = 0
        self.duplicate_inputs_rejected = 0
        self.session_skipped = 0
        self.errors = 0
        self._latency_samples = []
        self._start_time = time.time()

    def record_prediction(
        self,
        risk_level_str: str,
        latency_ms: float,
        insufficient_data: bool = False
    ) -> None:
        with self._lock:
            self.prediction_evaluations += 1
            self.risk_evaluations += 1
            self.decisions_generated += 1
            if insufficient_data:
                self.insufficient_data_predictions += 1
            if risk_level_str == "HIGH":
                self.high_risk_states += 1
            elif risk_level_str == "CRITICAL":
                self.critical_risk_states += 1
            self._latency_samples.append(latency_ms)
            if len(self._latency_samples) > 10000:
                self._latency_samples = self._latency_samples[-5000:]

    def record_malformed_input(self) -> None:
        with self._lock:
            self.malformed_inputs += 1

    def record_forecast_failure(self) -> None:
        with self._lock:
            self.forecast_failures += 1

    def record_duplicate_rejected(self) -> None:
        with self._lock:
            self.duplicate_inputs_rejected += 1

    def record_session_skipped(self) -> None:
        with self._lock:
            self.session_skipped += 1

    def record_error(self) -> None:
        with self._lock:
            self.errors += 1

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            samples = sorted(self._latency_samples) if self._latency_samples else [0.0]
            n = len(samples)
            avg_lat = sum(samples) / n
            p95_idx = min(n - 1, max(0, int(0.95 * n)))
            p99_idx = min(n - 1, max(0, int(0.99 * n)))
            return {
                "prediction_evaluations": self.prediction_evaluations,
                "risk_evaluations": self.risk_evaluations,
                "decisions_generated": self.decisions_generated,
                "insufficient_data_predictions": self.insufficient_data_predictions,
                "forecast_failures": self.forecast_failures,
                "malformed_inputs": self.malformed_inputs,
                "high_risk_states": self.high_risk_states,
                "critical_risk_states": self.critical_risk_states,
                "duplicate_inputs_rejected": self.duplicate_inputs_rejected,
                "session_skipped": self.session_skipped,
                "errors": self.errors,
                "avg_latency_ms": round(avg_lat, 3),
                "p95_latency_ms": round(samples[p95_idx], 3),
                "p99_latency_ms": round(samples[p99_idx], 3),
            }

    def reset(self) -> None:
        with self._lock:
            self._reset_unlocked()

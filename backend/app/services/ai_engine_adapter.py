"""
AI Engine Adapter — Sprint 9.

Provides a thread-safe per-venue registry that manages:
  1. MovementEngine (Sprint 6)
  2. EventIntelligenceEngine (Sprint 7)
  3. PredictionEngine (Sprint 8)
per venue_id.

Architecture:
    FastAPI endpoint → Service Layer → AIEngineAdapter → Sprint 6/7/8 AI Engines

Design constraints:
    - AI Engine lives in ai-engine/ which is a sibling directory.
    - sys.path is patched ONCE at import time to make ai-engine importable.
    - ALL AI Engine calls are synchronous (engines use threading.Lock internally).
    - NO MongoDB, NO Redis, NO persistence in Sprint 9.
    - NO business logic duplicated here — this adapter is a thin bridge only.
"""
import sys
import os
import threading
import logging
from typing import Dict, Optional, Tuple, Any

logger = logging.getLogger("crowdos.adapter")

# ---------------------------------------------------------------------------
# sys.path bootstrap — insert ai-engine ONCE before any AI Engine imports
# ---------------------------------------------------------------------------

_AI_ENGINE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "ai-engine")
)

if _AI_ENGINE_PATH not in sys.path:
    sys.path.insert(0, _AI_ENGINE_PATH)
    logger.debug(f"AI Engine path added to sys.path: {_AI_ENGINE_PATH}")


# ---------------------------------------------------------------------------
# Lazy AI Engine imports (delayed to allow sys.path setup first)
# ---------------------------------------------------------------------------

_AI_ENGINE_AVAILABLE = False
_IMPORT_ERROR: Optional[str] = None

try:
    from movement.engine.movement_engine import MovementEngine
    from movement.events.schema import (
        MovementEvent, EntryEvent, ExitEvent, MovementEventType, EventSource
    )
    from movement.state.occupancy import OccupancyState
    from intelligence.engine.intelligence_engine import EventIntelligenceEngine
    from prediction.engine.prediction_engine import PredictionEngine
    _AI_ENGINE_AVAILABLE = True
    logger.info("AI Engine modules (Movement, Intelligence, Prediction) imported successfully.")
except ImportError as _e:
    _IMPORT_ERROR = str(_e)
    logger.warning(
        f"AI Engine import failed — running in stub mode: {_e}. "
        "Set PYTHONPATH to ai-engine/ directory to enable full integration."
    )


# ---------------------------------------------------------------------------
# Stub classes for test isolation when AI Engine is not on sys.path
# ---------------------------------------------------------------------------

class _StubMovementEngine:
    def __init__(self):
        self.occupancy_tracker = type("StubOccTracker", (), {
            "record_entry": lambda self, *args, **kwargs: None,
            "record_exit": lambda self, *args, **kwargs: None,
            "get_state": lambda self, *args, **kwargs: None,
        })()

    def get_occupancy(self):
        return None

    def reset_all(self):
        pass


class _StubIntelligenceEngine:
    """Minimal stub used when ai-engine is not importable (test isolation)."""

    def __init__(self, venue_id: str = "default_venue", **kwargs):
        self.venue_id = venue_id
        self.session_manager = _StubSessionManager()
        self.flow_analytics = None
        self.occupancy_analytics = type("StubOccAnalytics", (), {
            "get_summary": lambda self: type("StubSummary", (), {
                "to_dict": lambda self: {"current_occupancy": 0, "gate_occupancy": {}}
            })()
        })()
        self.alert_manager = _StubAlertManager()

    def get_current_intelligence(self):
        return {
            "venue_id": self.venue_id,
            "flow": {},
            "occupancy": {"current_occupancy": 0, "gate_occupancy": {}},
            "density": {"density_level": "LOW", "congestion_level": "NORMAL", "occupancy_ratio": 0.0},
            "dwell": {"average_dwell": 0.0, "p95_dwell": 0.0},
            "peaks": {},
            "active_alerts_count": 0,
            "metrics": {},
        }

    def process_event(self, event):
        return {"status": "stub_processed"}

    def process_occupancy_state(self, state):
        return None

    def stop_session(self, session_id: str):
        return None

    def reset_all(self):
        pass


class _StubSessionManager:
    def __init__(self):
        self._sessions: Dict = {}
        self._active_id: Optional[str] = None
        self._lock = threading.Lock()

    def create_session(self, venue_id=None, session_id=None, metadata=None):
        import uuid
        sid = session_id or str(uuid.uuid4())
        sess = type("StubSession", (), {
            "session_id": sid, "venue_id": venue_id or "default_venue",
            "status": type("S", (), {"value": "CREATED"})(),
            "started_at": None, "stopped_at": None, "metadata": metadata or {},
            "max_duration_seconds": 86400.0,
            "to_dict": lambda self: {
                "session_id": self.session_id, "venue_id": self.venue_id,
                "status": "CREATED", "started_at": None, "stopped_at": None,
                "metadata": self.metadata,
            }
        })()
        self._sessions[sid] = sess
        return sess

    def start_session(self, session_id):
        if session_id in self._sessions:
            self._sessions[session_id].status = type("S", (), {"value": "ACTIVE"})()
            self._active_id = session_id
            return True
        return False

    def pause_session(self, session_id):
        if session_id in self._sessions:
            self._sessions[session_id].status = type("S", (), {"value": "PAUSED"})()
            return True
        return False

    def resume_session(self, session_id):
        if session_id in self._sessions:
            self._sessions[session_id].status = type("S", (), {"value": "ACTIVE"})()
            self._active_id = session_id
            return True
        return False

    def stop_session(self, session_id):
        if session_id in self._sessions:
            self._sessions[session_id].status = type("S", (), {"value": "STOPPED"})()
            if self._active_id == session_id:
                self._active_id = None
            return True
        return False

    def check_expiration(self, now_epoch=None):
        return []

    def get_session(self, session_id):
        return self._sessions.get(session_id)

    def get_active_session(self):
        if self._active_id:
            return self._sessions.get(self._active_id)
        return None

    def list_sessions(self):
        return list(self._sessions.values())


class _StubAlertManager:
    def get_active_alerts(self):
        return []

    def get_all_alerts(self):
        return []

    def get_resolved_alerts(self):
        return []


class _StubPredictionEngine:
    def __init__(self, venue_id="default_venue", **kwargs):
        self.venue_id = venue_id

    def predict(self, snapshot):
        return type("StubPrediction", (), {
            "status": "stub",
            "message": "Prediction engine not available",
            "venue_risk": None,
            "venue_trend": None,
            "venue_decision": None,
            "occupancy_forecast": None,
            "flow_forecast": None,
            "gate_results": {},
            "processing_time_ms": 0.0,
            "to_dict": lambda self: {
                "status": "stub",
                "message": "Prediction engine not available",
                "venue_risk": None,
            },
        })()

    def get_metrics(self):
        return {}

    def reset(self):
        pass


# ---------------------------------------------------------------------------
# Per-venue engine container
# ---------------------------------------------------------------------------

class VenueEngines:
    """Holds Sprint 6 movement engine + Sprint 7 intelligence engine + Sprint 8 prediction engine."""

    __slots__ = ("venue_id", "venue_capacity", "movement", "intelligence", "prediction")

    def __init__(
        self,
        venue_id: str,
        venue_capacity: int = 1000,
    ):
        self.venue_id = venue_id
        self.venue_capacity = venue_capacity

        if _AI_ENGINE_AVAILABLE:
            self.movement = MovementEngine()
            self.intelligence = EventIntelligenceEngine(venue_id=venue_id)
            self.prediction = PredictionEngine(venue_id=venue_id)
        else:
            self.movement = _StubMovementEngine()
            self.intelligence = _StubIntelligenceEngine(venue_id=venue_id)
            self.prediction = _StubPredictionEngine(venue_id=venue_id)


# ---------------------------------------------------------------------------
# Thread-safe venue registry singleton
# ---------------------------------------------------------------------------

class VenueEngineRegistry:
    """
    Thread-safe singleton registry mapping venue_id → VenueEngines.
    """

    _instance: Optional["VenueEngineRegistry"] = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "VenueEngineRegistry":
        with cls._instance_lock:
            if cls._instance is None:
                obj = super().__new__(cls)
                obj._registry: Dict[str, VenueEngines] = {}
                obj._registry_lock = threading.Lock()
                cls._instance = obj
        return cls._instance

    def get_or_create(self, venue_id: str, venue_capacity: int = 1000) -> VenueEngines:
        """
        Return existing VenueEngines for venue_id, or create a new one.
        Thread-safe.
        """
        with self._registry_lock:
            if venue_id not in self._registry:
                logger.info(f"Creating new engine triad (Movement, Intelligence, Prediction) for venue_id={venue_id!r}")
                self._registry[venue_id] = VenueEngines(
                    venue_id=venue_id,
                    venue_capacity=venue_capacity,
                )
            return self._registry[venue_id]

    def get(self, venue_id: str) -> Optional[VenueEngines]:
        """Return existing VenueEngines or None (does not create)."""
        with self._registry_lock:
            return self._registry.get(venue_id)

    def find_venue_by_session(self, session_id: str) -> Optional[Tuple[str, VenueEngines]]:
        """Look up venue_id and VenueEngines by session_id across registered venues."""
        with self._registry_lock:
            for v_id, engines in self._registry.items():
                if engines.intelligence.session_manager.get_session(session_id):
                    return v_id, engines
        return None

    def list_venue_ids(self):
        with self._registry_lock:
            return list(self._registry.keys())

    def update_capacity(self, venue_id: str, venue_capacity: int) -> None:
        with self._registry_lock:
            if venue_id in self._registry:
                self._registry[venue_id].venue_capacity = venue_capacity

    def reset_venue(self, venue_id: str) -> bool:
        """Reset all engine state for a venue (for testing)."""
        with self._registry_lock:
            engines = self._registry.get(venue_id)
            if engines:
                try:
                    engines.movement.reset_all()
                    engines.intelligence.reset_all()
                    engines.prediction.reset()
                except Exception:
                    pass
                del self._registry[venue_id]
                return True
            return False

    def clear_all(self) -> None:
        """Reset entire registry (for testing)."""
        with self._registry_lock:
            for engines in self._registry.values():
                try:
                    engines.movement.reset_all()
                    engines.intelligence.reset_all()
                    engines.prediction.reset()
                except Exception:
                    pass
            self._registry.clear()

    @property
    def is_ai_engine_available(self) -> bool:
        return _AI_ENGINE_AVAILABLE

    @property
    def import_error(self) -> Optional[str]:
        return _IMPORT_ERROR


# Module-level singleton
venue_registry = VenueEngineRegistry()

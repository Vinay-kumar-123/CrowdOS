"""
Camera AI Vision Pipeline Service — Sprint 17.

Connects the live Camera Runtime to CrowdOS's frozen AI Vision Engines:
    FrameItem (FrameConsumer)
      ↓
    DetectionEngine (Sprint 2/3) -> FrameDetectionResult
      ↓
    TrackingEngine (Sprint 4 ByteTrack) -> TrackingResult
      ↓
    MovementEngine (Sprint 6 Gate & Movement Intelligence) -> List[MovementEvent]
      ↓
    Structured Movement Event Dicts -> EventService.ingest_event()

Invariants:
- STRICT NON-FABRICATION: If no persons are detected or no gate crossing occurs,
  zero events are generated. Never invent synthetic detections or crossings.
- ISOLATION: Trackers are isolated per camera in TrackingEngine. State trajectories
  are isolated per (camera_id, gate_id, track_id) in MovementEngine.
- THREAD SAFETY: All underlying AI engines use internal locks for concurrent safety.
- GRACEFUL DEGRADATION: If AI engine modules are unavailable or frame is malformed,
  fails safely without unhandled exceptions.
"""
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
import numpy as np

logger = logging.getLogger("crowdos.camera_pipeline")

# Lazy import AI Engine components with fallback
_AI_ENGINE_AVAILABLE = False
try:
    from detection.engine.detection_engine import DetectionEngine
    from tracking.engine.tracking_engine import TrackingEngine
    from movement.engine.movement_engine import MovementEngine
    from movement.config.gate_config import GateConfig, GateType
    from movement.events.schema import MovementEvent, MovementEventType
    _AI_ENGINE_AVAILABLE = True
except Exception as _e:
    logger.warning(f"AI Engine modules could not be imported in CameraAIPipeline: {_e}")


class CameraAIPipeline:
    """
    Orchestrates frame-level vision processing across Detection, Tracking,
    and Movement engines for live camera streams.
    """

    def __init__(
        self,
        detection_engine: Optional[Any] = None,
        tracking_engine: Optional[Any] = None,
        movement_engine: Optional[Any] = None,
    ):
        self._is_available = _AI_ENGINE_AVAILABLE
        if self._is_available:
            self._detection_engine = detection_engine or DetectionEngine()
            if hasattr(self._detection_engine, "initialize"):
                self._detection_engine.initialize()
            self._tracking_engine = tracking_engine or TrackingEngine()
            self._movement_engine = movement_engine or MovementEngine()
        else:
            self._detection_engine = None
            self._tracking_engine = None
            self._movement_engine = None

    @property
    def is_available(self) -> bool:
        return self._is_available

    def sync_gate_config(
        self,
        movement_engine: Any,
        camera_id: str,
        gate_id: str,
        venue_id: str = "default_venue",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Ensure gate configuration exists in MovementEngine.gate_manager for this camera.
        If not yet registered, registers a bidirectional line gate across the camera view.
        """
        if not movement_engine or not hasattr(movement_engine, "gate_manager"):
            return

        gate_mgr = movement_engine.gate_manager
        existing_gate = gate_mgr.get_gate(gate_id)
        if existing_gate is not None:
            # Already configured
            return

        meta = metadata or {}
        gate_name = meta.get("gate_name", f"Gate {gate_id}")
        zone_coords = meta.get("zone_coordinates") or meta.get("line_coordinates", [[0.0, 240.0], [640.0, 240.0]])
        normal = meta.get("normal_vector", [0.0, 1.0])

        gate_type_str = str(meta.get("gate_type", "BIDIRECTIONAL")).upper()
        try:
            gate_type = GateType[gate_type_str]
        except Exception:
            gate_type = GateType.BIDIRECTIONAL

        try:
            gate = GateConfig(
                gate_id=gate_id,
                gate_name=gate_name,
                camera_id=camera_id,
                gate_type=gate_type,
                zone_type=meta.get("zone_type", "LINE"),
                zone_coordinates=zone_coords,
                normal_vector=normal,
                venue_id=venue_id,
            )
            gate_mgr.add_gate(gate)
            logger.info(
                f"Configured gate '{gate_id}' for camera '{camera_id}' in venue '{venue_id}'",
                extra={"camera_id": camera_id, "gate_id": gate_id, "venue_id": venue_id}
            )
        except Exception as ge:
            logger.error(f"Failed to configure gate '{gate_id}' for camera '{camera_id}': {ge}")

    def process_frame(
        self,
        camera_id: str,
        venue_id: str = "default_venue",
        gate_id: str = "default_gate",
        frame_item: Any = None,
        movement_engine: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        frame: Optional[Any] = None,
        frame_number: Optional[int] = None,
        timestamp: Optional[float] = None,
        gate_config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Process a single frame or FrameItem through Detection -> Tracking -> Movement.

        Returns a list of structured event dictionaries for genuine crossings.
        Returns [] if no detections, no crossings, or on any validation failure.
        """
        if not self._is_available or self._detection_engine is None or self._tracking_engine is None:
            return []

        # Resolve frame array, frame number, and timestamp
        if frame is not None:
            actual_frame = frame
            fn = frame_number if frame_number is not None else 0
            ts = timestamp if timestamp is not None else time.time()
        elif hasattr(frame_item, "frame"):
            actual_frame = frame_item.frame
            fn = int(getattr(frame_item, "frame_number", frame_number or 0))
            ts = float(getattr(frame_item, "timestamp", timestamp or time.time()))
        elif isinstance(frame_item, np.ndarray):
            actual_frame = frame_item
            fn = int(frame_number if frame_number is not None else 0)
            ts = float(timestamp if timestamp is not None else time.time())
        else:
            actual_frame = frame_item
            fn = int(frame_number if frame_number is not None else 0)
            ts = float(timestamp if timestamp is not None else time.time())

        # 1. Frame validation
        if actual_frame is None or not isinstance(actual_frame, np.ndarray) or actual_frame.size == 0 or actual_frame.ndim != 3:
            return []

        active_movement_engine = movement_engine or self._movement_engine
        meta = dict(metadata or {})
        if gate_config:
            meta.update(gate_config)

        # 2. Ensure gate is registered in MovementEngine
        if gate_id and active_movement_engine:
            self.sync_gate_config(active_movement_engine, camera_id, gate_id, venue_id, meta)

        # 3. Detection Engine (Sprint 2/3)
        try:
            detection_result = self._detection_engine.detect_persons(
                frame=actual_frame,
                camera_id=camera_id,
                frame_number=fn,
            )
        except Exception as de:
            logger.error(f"DetectionEngine error on camera {camera_id}: {de}")
            return []

        if not detection_result or not getattr(detection_result, "detections", None):
            # No persons detected — strict non-fabrication

            return []

        # 4. Tracking Engine (Sprint 4 ByteTrack)
        try:
            tracking_result = self._tracking_engine.process_detections(
                detection_result=detection_result,
                frame=actual_frame,
            )
        except Exception as te:
            logger.error(f"TrackingEngine error on camera {camera_id}: {te}")
            return []

        if not tracking_result or not getattr(tracking_result, "tracks", None):
            # No active tracks — strict non-fabrication
            return []

        # 5. Movement Engine (Sprint 6 Gate Crossing Analysis)
        if not active_movement_engine or not hasattr(active_movement_engine, "process_frame"):
            return []

        try:
            movement_events = active_movement_engine.process_frame(tracking_result)
        except Exception as me:
            logger.error(f"MovementEngine error on camera {camera_id}: {me}")
            return []

        if not movement_events:
            # No gate crossing detected — strict non-fabrication
            return []

        # 6. Format genuine movement events
        results = []
        for ev in movement_events:
            ev_type_raw = getattr(ev, "event_type", None)
            ev_type = ev_type_raw.value if hasattr(ev_type_raw, "value") else str(ev_type_raw)
            if ev_type.upper() not in ("ENTRY", "EXIT"):
                continue

            identity_id = getattr(ev, "identity_id", "UNKNOWN")
            visitor_id = identity_id if identity_id and identity_id != "UNKNOWN" else None

            results.append({
                "event_type": ev_type.upper(),
                "gate_id": getattr(ev, "gate_id", gate_id),
                "track_id": str(getattr(ev, "track_id", f"trk_{fn}")),
                "detection_id": str(getattr(ev, "detection_id", "")),
                "identity_id": identity_id,
                "visitor_id": visitor_id,
                "dwell_time": getattr(ev, "dwell_time", None),
                "direction": getattr(ev, "direction", ev_type.upper()),
            })

        return results



    @property
    def is_ready(self) -> bool:
        """Indicates whether AI vision models and pipeline dependencies are ready."""
        return self._is_available and self._detection_engine is not None and self._tracking_engine is not None


# Module singleton instance
camera_ai_pipeline = CameraAIPipeline()


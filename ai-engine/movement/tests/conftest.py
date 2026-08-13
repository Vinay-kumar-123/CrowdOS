"""
Sprint 6 — Movement Intelligence Engine Test Fixtures and Helpers
"""
import uuid
import pytest
import time
from datetime import datetime, timezone
from typing import List, Tuple, Optional

from detection.results.schema import BoundingBox
from tracking.results.schema import TrackingResult, TrackedPerson, TrackState
from movement.config.gate_config import GateConfig, GateType, GateManager
from movement.state.occupancy import OccupancyTracker
from movement.state.journey import JourneyTracker
from movement.events.deduplicator import EventDeduplicator
from movement.events.validator import MovementEventValidator
from movement.engine.movement_engine import MovementEngine


def make_gate(
    gate_id: str = "gate_main",
    gate_name: str = "Main Gate",
    camera_id: str = "cam_01",
    gate_type: GateType = GateType.BIDIRECTIONAL,
    line_start: Tuple[float, float] = (0.0, 200.0),
    line_end: Tuple[float, float] = (640.0, 200.0),
    normal_vector: Optional[List[float]] = None,
    venue_id: str = "venue_01"
) -> GateConfig:
    """Build a virtual line gate configuration."""
    coords = [[line_start[0], line_start[1]], [line_end[0], line_end[1]]]
    return GateConfig(
        gate_id=gate_id,
        gate_name=gate_name,
        camera_id=camera_id,
        gate_type=gate_type,
        zone_type="LINE",
        zone_coordinates=coords,
        normal_vector=normal_vector,
        venue_id=venue_id
    )


def make_polygon_gate(
    gate_id: str = "gate_poly",
    camera_id: str = "cam_01",
    gate_type: GateType = GateType.BIDIRECTIONAL,
    polygon: Optional[List[Tuple[float, float]]] = None
) -> GateConfig:
    """Build a polygon zone gate configuration."""
    if polygon is None:
        polygon = [(100.0, 100.0), (400.0, 100.0), (400.0, 400.0), (100.0, 400.0)]
    coords = [[p[0], p[1]] for p in polygon]
    return GateConfig(
        gate_id=gate_id,
        gate_name="Polygon Gate",
        camera_id=camera_id,
        gate_type=gate_type,
        zone_type="POLYGON",
        zone_coordinates=coords
    )


def make_tracked_person(
    track_id: str = "1",
    camera_id: str = "cam_01",
    frame_number: int = 1,
    cx: float = 320.0,
    cy: float = 150.0,
    track_state: TrackState = TrackState.ACTIVE,
    detection_id: Optional[str] = None
) -> TrackedPerson:
    """Build a synthetic TrackedPerson at center (cx, cy)."""
    did = detection_id or str(uuid.uuid4())
    return TrackedPerson(
        track_id=track_id,
        detection_id=did,
        camera_id=camera_id,
        frame_number=frame_number,
        bbox=BoundingBox(x1=cx - 30, y1=cy - 60, x2=cx + 30, y2=cy + 60),
        confidence=0.90,
        center=(cx, cy),
        track_state=track_state
    )


def make_tracking_result(
    camera_id: str = "cam_01",
    frame_number: int = 1,
    tracks: Optional[List[TrackedPerson]] = None
) -> TrackingResult:
    """Build a synthetic TrackingResult."""
    tracks = tracks or []
    return TrackingResult(
        frame_number=frame_number,
        camera_id=camera_id,
        tracking_time_ms=2.0,
        total_active_tracks=len(tracks),
        total_lost_tracks=0,
        tracks=tracks
    )


def make_engine_with_line_gate(
    camera_id: str = "cam_01",
    gate_id: str = "gate_main",
    line_y: float = 200.0,
    gate_type: GateType = GateType.BIDIRECTIONAL,
    dedup_window: float = 0.1
) -> MovementEngine:
    """Build a MovementEngine with a single horizontal line gate for testing."""
    gate = make_gate(
        gate_id=gate_id,
        camera_id=camera_id,
        gate_type=gate_type,
        line_start=(0.0, line_y),
        line_end=(640.0, line_y)
    )
    gate_mgr = GateManager()
    gate_mgr.add_gate(gate)
    return MovementEngine(
        gate_manager=gate_mgr,
        deduplicator=EventDeduplicator(window_seconds=dedup_window)
    )


@pytest.fixture
def line_engine():
    return make_engine_with_line_gate()


@pytest.fixture
def gate_manager():
    mgr = GateManager()
    mgr.add_gate(make_gate())
    return mgr

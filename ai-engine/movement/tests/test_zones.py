"""Tests for LineZone and PolygonZone crossing evaluations."""
import pytest
from movement.zones.line_zone import LineZone
from movement.zones.polygon_zone import PolygonZone
from movement.zones.base_zone import CrossingDirection


LINE_START = (0.0, 200.0)
LINE_END = (640.0, 200.0)


def make_line_zone(normal=None) -> LineZone:
    return LineZone("z1", "Main Gate Line", LINE_START, LINE_END, normal)


def make_polygon_zone() -> PolygonZone:
    return PolygonZone("z2", "Polygon Zone",
                       [(100.0, 100.0), (400.0, 100.0), (400.0, 400.0), (100.0, 400.0)])


# ─────────────────────────── LineZone ─────────────────────────────

def test_line_crossing_top_to_bottom_detects_crossing():
    """Trajectory moving from y=100 (above) to y=300 (below) must cross the y=200 line."""
    zone = make_line_zone()
    trajectory = [(320.0, 100.0), (320.0, 150.0), (320.0, 250.0), (320.0, 300.0)]
    result = zone.evaluate_trajectory(trajectory, min_crossing_distance=10.0)
    assert result.has_crossed


def test_line_crossing_bottom_to_top_detects_crossing():
    """Trajectory moving from y=300 to y=100 must also cross."""
    zone = make_line_zone()
    trajectory = [(320.0, 300.0), (320.0, 250.0), (320.0, 150.0), (320.0, 100.0)]
    result = zone.evaluate_trajectory(trajectory, min_crossing_distance=10.0)
    assert result.has_crossed


def test_line_no_crossing_same_side():
    """Trajectory entirely above line must not cross."""
    zone = make_line_zone()
    trajectory = [(320.0, 50.0), (320.0, 80.0), (320.0, 100.0), (320.0, 150.0)]
    result = zone.evaluate_trajectory(trajectory, min_crossing_distance=10.0)
    assert not result.has_crossed


def test_line_no_crossing_stationary():
    """Stationary trajectory at y=200 (on line) with tiny jitter must not cross."""
    zone = make_line_zone()
    trajectory = [(320.0, 200.0), (321.0, 200.0), (320.5, 200.0), (320.0, 200.0)]
    result = zone.evaluate_trajectory(trajectory, min_crossing_distance=20.0)
    assert not result.has_crossed


def test_line_no_crossing_parallel_motion():
    """Trajectory moving parallel to the line (constant y) must not cross."""
    zone = make_line_zone()
    trajectory = [(100.0, 150.0), (200.0, 150.0), (300.0, 150.0), (400.0, 150.0)]
    result = zone.evaluate_trajectory(trajectory, min_crossing_distance=10.0)
    assert not result.has_crossed


def test_line_direction_with_normal_vector_entry():
    """Normal vector pointing downward → trajectory moving downward = ENTRY."""
    zone = LineZone("z1", "Test", LINE_START, LINE_END, normal_vector=(0.0, 1.0))
    trajectory = [(320.0, 100.0), (320.0, 150.0), (320.0, 250.0), (320.0, 300.0)]
    result = zone.evaluate_trajectory(trajectory, min_crossing_distance=10.0)
    assert result.has_crossed
    assert result.direction == CrossingDirection.ENTRY


def test_line_direction_with_normal_vector_exit():
    """Normal vector pointing downward → trajectory moving upward = EXIT."""
    zone = LineZone("z1", "Test", LINE_START, LINE_END, normal_vector=(0.0, 1.0))
    trajectory = [(320.0, 300.0), (320.0, 250.0), (320.0, 150.0), (320.0, 100.0)]
    result = zone.evaluate_trajectory(trajectory, min_crossing_distance=10.0)
    assert result.has_crossed
    assert result.direction == CrossingDirection.EXIT


def test_line_crossing_insufficient_points():
    """Single point trajectory must not evaluate."""
    zone = make_line_zone()
    result = zone.evaluate_trajectory([(320.0, 100.0)], min_crossing_distance=10.0)
    assert not result.has_crossed


def test_line_crossing_returns_confidence():
    """A valid crossing must have confidence > 0."""
    zone = make_line_zone()
    trajectory = [(320.0, 50.0), (320.0, 150.0), (320.0, 250.0), (320.0, 350.0)]
    result = zone.evaluate_trajectory(trajectory, min_crossing_distance=10.0)
    if result.has_crossed:
        assert result.confidence > 0.0


# ─────────────────────────── PolygonZone ─────────────────────────

def test_polygon_entry_detection():
    """Trajectory from outside to inside polygon must detect ENTRY."""
    zone = make_polygon_zone()
    trajectory = [(50.0, 50.0), (100.0, 100.0), (200.0, 200.0), (250.0, 250.0)]
    result = zone.evaluate_trajectory(trajectory, min_crossing_distance=10.0)
    assert result.has_crossed
    assert result.direction == CrossingDirection.ENTRY


def test_polygon_exit_detection():
    """Trajectory from inside to outside polygon must detect EXIT."""
    zone = make_polygon_zone()
    trajectory = [(250.0, 250.0), (200.0, 200.0), (80.0, 80.0), (20.0, 20.0)]
    result = zone.evaluate_trajectory(trajectory, min_crossing_distance=10.0)
    assert result.has_crossed
    assert result.direction == CrossingDirection.EXIT


def test_polygon_no_crossing_if_always_outside():
    """Trajectory entirely outside polygon must not cross."""
    zone = make_polygon_zone()
    trajectory = [(10.0, 10.0), (20.0, 10.0), (30.0, 10.0), (50.0, 10.0)]
    result = zone.evaluate_trajectory(trajectory, min_crossing_distance=10.0)
    assert not result.has_crossed


def test_polygon_no_crossing_if_always_inside():
    """Trajectory entirely inside polygon must not cross."""
    zone = make_polygon_zone()
    trajectory = [(200.0, 200.0), (210.0, 200.0), (220.0, 200.0), (230.0, 200.0)]
    result = zone.evaluate_trajectory(trajectory, min_crossing_distance=10.0)
    assert not result.has_crossed


def test_polygon_get_info():
    zone = make_polygon_zone()
    info = zone.get_info()
    assert info["zone_type"] == "POLYGON"
    assert len(info["polygon_points"]) == 4

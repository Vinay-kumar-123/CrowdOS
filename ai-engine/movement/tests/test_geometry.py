"""Tests for 2D geometry functions."""
import math
import pytest
from movement.utils.geometry import (
    ccw_orientation, line_segments_intersect, signed_distance_to_line,
    point_in_polygon, distance, on_segment
)


def test_ccw_orientation_left():
    """Point to the left of vector p->q returns positive."""
    p, q, r = (0.0, 0.0), (1.0, 0.0), (0.5, 1.0)
    assert ccw_orientation(p, q, r) > 0


def test_ccw_orientation_right():
    """Point to the right of vector p->q returns negative."""
    p, q, r = (0.0, 0.0), (1.0, 0.0), (0.5, -1.0)
    assert ccw_orientation(p, q, r) < 0


def test_ccw_orientation_collinear():
    """Collinear points return zero."""
    p, q, r = (0.0, 0.0), (1.0, 1.0), (2.0, 2.0)
    assert ccw_orientation(p, q, r) == 0


def test_distance_basic():
    assert abs(distance((0, 0), (3, 4)) - 5.0) < 1e-6


def test_line_segments_intersect_crossing():
    """Two crossing segments must intersect."""
    assert line_segments_intersect(
        (0.0, 0.0), (640.0, 0.0),
        (320.0, -100.0), (320.0, 100.0)
    )


def test_line_segments_no_intersect_parallel():
    """Two parallel horizontal segments must not intersect."""
    assert not line_segments_intersect(
        (0.0, 0.0), (640.0, 0.0),
        (0.0, 100.0), (640.0, 100.0)
    )


def test_line_segments_no_intersect_same_side():
    """Two T-shape segments that don't cross must not intersect."""
    assert not line_segments_intersect(
        (0.0, 0.0), (100.0, 0.0),
        (200.0, -50.0), (200.0, -10.0)
    )


def test_signed_distance_left_is_positive():
    """Point above horizontal line (left of rightward vector) is positive."""
    dist = signed_distance_to_line((320.0, 100.0), (0.0, 200.0), (640.0, 200.0))
    assert dist > 0


def test_signed_distance_right_is_negative():
    """Point below horizontal line is negative."""
    dist = signed_distance_to_line((320.0, 300.0), (0.0, 200.0), (640.0, 200.0))
    assert dist < 0


def test_signed_distance_on_line_is_zero():
    """Point on the line segment has near-zero signed distance."""
    dist = signed_distance_to_line((320.0, 200.0), (0.0, 200.0), (640.0, 200.0))
    assert abs(dist) < 1e-6


def test_point_in_polygon_inside():
    square = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
    assert point_in_polygon((50.0, 50.0), square)


def test_point_in_polygon_outside():
    square = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
    assert not point_in_polygon((150.0, 50.0), square)


def test_point_in_polygon_empty():
    assert not point_in_polygon((50.0, 50.0), [])


def test_point_in_polygon_triangle():
    triangle = [(0.0, 0.0), (200.0, 0.0), (100.0, 200.0)]
    assert point_in_polygon((100.0, 50.0), triangle)
    assert not point_in_polygon((0.0, 150.0), triangle)

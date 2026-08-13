"""Tests for DirectionDetector trajectory movement vector computation."""
import math
import pytest
from movement.engine.direction import DirectionDetector


def test_direction_downward():
    det = DirectionDetector()
    traj = [(100.0, 0.0), (100.0, 50.0), (100.0, 100.0)]
    dx, dy, mag = det.compute_movement_vector(traj)
    assert dy > 0
    assert abs(mag - 100.0) < 1.0


def test_direction_upward():
    det = DirectionDetector()
    traj = [(100.0, 300.0), (100.0, 200.0), (100.0, 100.0)]
    dx, dy, mag = det.compute_movement_vector(traj)
    assert dy < 0


def test_direction_stationary_returns_zero():
    det = DirectionDetector()
    traj = [(200.0, 200.0), (200.0, 200.0), (200.0, 200.0)]
    dx, dy, mag = det.compute_movement_vector(traj)
    assert mag == 0.0


def test_direction_single_point_returns_zero():
    det = DirectionDetector()
    dx, dy, mag = det.compute_movement_vector([(100.0, 100.0)])
    assert dx == 0.0 and dy == 0.0 and mag == 0.0


def test_direction_empty_returns_zero():
    det = DirectionDetector()
    dx, dy, mag = det.compute_movement_vector([])
    assert mag == 0.0


def test_direction_normalized():
    """Unit vector dx^2 + dy^2 = 1 for non-zero trajectory."""
    det = DirectionDetector()
    traj = [(0.0, 0.0), (3.0, 4.0)]
    dx, dy, mag = det.compute_movement_vector(traj)
    assert abs(math.sqrt(dx**2 + dy**2) - 1.0) < 1e-6
    assert abs(mag - 5.0) < 1e-6

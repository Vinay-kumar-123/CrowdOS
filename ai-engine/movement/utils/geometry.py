import math
from typing import Tuple, List, NamedTuple, Optional


class Point(NamedTuple):
    x: float
    y: float


def distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Euclidean distance between two 2D points."""
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def ccw_orientation(p: Tuple[float, float], q: Tuple[float, float], r: Tuple[float, float]) -> float:
    """
    Compute 2D cross product of vectors (q - p) and (r - p).
    Returns:
      > 0: r is to the left of directed line segment p->q (counter-clockwise)
      < 0: r is to the right of directed line segment p->q (clockwise)
      == 0: p, q, r are collinear
    """
    return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])


def on_segment(p: Tuple[float, float], q: Tuple[float, float], r: Tuple[float, float]) -> bool:
    """Given collinear points p, q, r, check if point q lies on line segment p-r."""
    return (
        min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and
        min(p[1], r[1]) <= q[1] <= max(p[1], r[1])
    )


def line_segments_intersect(
    p1: Tuple[float, float],
    q1: Tuple[float, float],
    p2: Tuple[float, float],
    q2: Tuple[float, float]
) -> bool:
    """
    Determine if line segment p1-q1 intersects line segment p2-q2.
    Uses 2D orientation test.
    """
    o1 = ccw_orientation(p1, q1, p2)
    o2 = ccw_orientation(p1, q1, q2)
    o3 = ccw_orientation(p2, q2, p1)
    o4 = ccw_orientation(p2, q2, q1)

    # General case: segments cross each other
    if ((o1 > 0 and o2 < 0) or (o1 < 0 and o2 > 0)) and ((o3 > 0 and o4 < 0) or (o3 < 0 and o4 > 0)):
        return True

    # Special Cases (collinear points lying on segment)
    if o1 == 0 and on_segment(p1, p2, q1): return True
    if o2 == 0 and on_segment(p1, q2, q1): return True
    if o3 == 0 and on_segment(p2, p1, q2): return True
    if o4 == 0 and on_segment(p2, q1, q2): return True

    return False


def signed_distance_to_line(
    p: Tuple[float, float],
    l1: Tuple[float, float],
    l2: Tuple[float, float]
) -> float:
    """
    Compute signed perpendicular distance from point p to directed line segment l1->l2.
    Positive value indicates point is on the left side of the vector l1->l2.
    Negative value indicates point is on the right side.
    """
    dx = l2[0] - l1[0]
    dy = l2[1] - l1[1]
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return 0.0

    # Cross product gives signed area of parallelogram; divide by length for perpendicular height
    cross = (l2[0] - l1[0]) * (l1[1] - p[1]) - (l1[0] - p[0]) * (l2[1] - l1[1])
    return cross / length


def point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """
    Ray-casting algorithm to determine whether point (x, y) is inside a polygon.
    Polygon is a list of 2D vertex tuples.
    """
    if not polygon or len(polygon) < 3:
        return False

    x, y = point
    inside = False
    n = len(polygon)

    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside

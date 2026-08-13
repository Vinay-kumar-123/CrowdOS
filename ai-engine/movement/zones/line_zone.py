import math
from typing import List, Tuple, Dict, Any, Optional
from movement.zones.base_zone import BaseZone, ZoneType, CrossingResult, CrossingDirection
from movement.utils.geometry import (
    line_segments_intersect, signed_distance_to_line, distance, ccw_orientation
)


class LineZone(BaseZone):
    """
    Virtual Line Crossing Zone.
    Evaluates line crossings using 2D vector segment intersection and signed side-of-line transitions.
    """

    def __init__(
        self,
        zone_id: str,
        zone_name: str,
        line_start: Tuple[float, float],
        line_end: Tuple[float, float],
        normal_vector: Optional[Tuple[float, float]] = None
    ):
        super().__init__(zone_id, zone_name, ZoneType.LINE)
        self.line_start = (float(line_start[0]), float(line_start[1]))
        self.line_end = (float(line_end[0]), float(line_end[1]))
        self.normal_vector = normal_vector

    def evaluate_trajectory(
        self,
        trajectory: List[Tuple[float, float]],
        min_crossing_distance: float = 5.0
    ) -> CrossingResult:
        if not trajectory or len(trajectory) < 2:
            return CrossingResult(has_crossed=False)

        # Check latest movement step (p_prev -> p_curr)
        p_curr = trajectory[-1]
        p_prev = trajectory[-2]

        # Calculate displacement over full trajectory window
        total_disp = distance(trajectory[0], p_curr)
        step_disp = distance(p_prev, p_curr)

        # 1. Minimum displacement check (reject jitter or stationary standing)
        if total_disp < min_crossing_distance and step_disp < min_crossing_distance:
            return CrossingResult(has_crossed=False, displacement=total_disp)

        # 2. Check segment intersection between movement step and virtual line
        # Check both last step (p_prev -> p_curr) and full window (trajectory[0] -> p_curr)
        intersects_step = line_segments_intersect(p_prev, p_curr, self.line_start, self.line_end)
        intersects_window = line_segments_intersect(trajectory[0], p_curr, self.line_start, self.line_end)

        if not (intersects_step or intersects_window):
            return CrossingResult(has_crossed=False, displacement=total_disp)

        # 3. Signed side-of-line transition
        dist_start = signed_distance_to_line(trajectory[0], self.line_start, self.line_end)
        dist_end = signed_distance_to_line(p_curr, self.line_start, self.line_end)

        # Parallel movement or staying on same side -> no crossing
        if (dist_start > 0 and dist_end > 0) or (dist_start < 0 and dist_end < 0):
            return CrossingResult(has_crossed=False, displacement=total_disp)

        # Determine direction based on side transition
        direction = CrossingDirection.UNKNOWN
        if self.normal_vector is not None:
            # Custom normal vector: dot product of movement vector with normal
            move_vec = (p_curr[0] - trajectory[0][0], p_curr[1] - trajectory[0][1])
            dot = move_vec[0] * self.normal_vector[0] + move_vec[1] * self.normal_vector[1]
            direction = CrossingDirection.ENTRY if dot >= 0 else CrossingDirection.EXIT
        else:
            # Default convention: positive-to-negative signed distance side = ENTRY
            # (for a rightward line, above→below = ENTRY, below→above = EXIT)
            if dist_start >= 0 and dist_end < 0:
                direction = CrossingDirection.ENTRY
            elif dist_start <= 0 and dist_end > 0:
                direction = CrossingDirection.EXIT

        # Compute crossing intersection point approximation
        crossing_pt = (
            (p_prev[0] + p_curr[0]) / 2.0,
            (p_prev[1] + p_curr[1]) / 2.0
        )

        confidence = min(1.0, max(0.5, total_disp / (min_crossing_distance * 2.0)))

        return CrossingResult(
            has_crossed=True,
            direction=direction,
            confidence=round(confidence, 2),
            crossing_point=crossing_pt,
            displacement=round(total_disp, 2)
        )

    def get_info(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "zone_type": "LINE",
            "line_start": self.line_start,
            "line_end": self.line_end,
            "normal_vector": self.normal_vector
        }

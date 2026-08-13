import math
from typing import List, Tuple
from movement.config.settings import movement_settings


class DirectionDetector:
    """
    Trajectory Movement Direction Solver.
    Computes displacement vector and normalized direction from a sequence of center points.
    Does NOT classify direction from a single frame.
    """

    def compute_movement_vector(
        self,
        trajectory: List[Tuple[float, float]]
    ) -> Tuple[float, float, float]:
        """
        Given trajectory [p(0), ..., p(N)], compute (dx, dy, magnitude).
        """
        if not trajectory or len(trajectory) < 2:
            return (0.0, 0.0, 0.0)

        start_p = trajectory[0]
        end_p = trajectory[-1]

        dx = end_p[0] - start_p[0]
        dy = end_p[1] - start_p[1]
        magnitude = math.hypot(dx, dy)

        if magnitude < 1e-6:
            return (0.0, 0.0, 0.0)

        return (dx / magnitude, dy / magnitude, magnitude)

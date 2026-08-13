from typing import List, Tuple, Dict, Any
from movement.zones.base_zone import BaseZone, ZoneType, CrossingResult, CrossingDirection
from movement.utils.geometry import point_in_polygon, distance


class PolygonZone(BaseZone):
    """
    Polygon Zone Boundary.
    Evaluates entry/exit transitions based on point-in-polygon containment state changes.
    """

    def __init__(
        self,
        zone_id: str,
        zone_name: str,
        polygon_points: List[Tuple[float, float]]
    ):
        super().__init__(zone_id, zone_name, ZoneType.POLYGON)
        self.polygon_points = [(float(p[0]), float(p[1])) for p in polygon_points]

    def evaluate_trajectory(
        self,
        trajectory: List[Tuple[float, float]],
        min_crossing_distance: float = 5.0
    ) -> CrossingResult:
        if not trajectory or len(trajectory) < 2 or len(self.polygon_points) < 3:
            return CrossingResult(has_crossed=False)

        p_start = trajectory[0]
        p_curr = trajectory[-1]

        disp = distance(p_start, p_curr)
        if disp < min_crossing_distance:
            return CrossingResult(has_crossed=False, displacement=disp)

        start_inside = point_in_polygon(p_start, self.polygon_points)
        curr_inside = point_in_polygon(p_curr, self.polygon_points)

        if not start_inside and curr_inside:
            return CrossingResult(
                has_crossed=True,
                direction=CrossingDirection.ENTRY,
                confidence=0.90,
                crossing_point=p_curr,
                displacement=round(disp, 2)
            )
        elif start_inside and not curr_inside:
            return CrossingResult(
                has_crossed=True,
                direction=CrossingDirection.EXIT,
                confidence=0.90,
                crossing_point=p_curr,
                displacement=round(disp, 2)
            )

        return CrossingResult(has_crossed=False, displacement=round(disp, 2))

    def is_point_inside(self, point: Tuple[float, float]) -> bool:
        return point_in_polygon(point, self.polygon_points)

    def get_info(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "zone_type": "POLYGON",
            "polygon_points": self.polygon_points
        }

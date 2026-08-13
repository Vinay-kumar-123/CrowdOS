from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Tuple, Dict, Any, Optional


class ZoneType(str, Enum):
    LINE = "LINE"
    POLYGON = "POLYGON"
    RESTRICTED = "RESTRICTED"
    QUEUE = "QUEUE"
    EMERGENCY = "EMERGENCY"


class CrossingDirection(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    UNKNOWN = "UNKNOWN"


class CrossingResult:
    """
    Outcome payload of a zone crossing evaluation.
    """
    def __init__(
        self,
        has_crossed: bool,
        direction: CrossingDirection = CrossingDirection.UNKNOWN,
        confidence: float = 0.0,
        crossing_point: Optional[Tuple[float, float]] = None,
        displacement: float = 0.0
    ):
        self.has_crossed = has_crossed
        self.direction = direction
        self.confidence = float(confidence)
        self.crossing_point = crossing_point
        self.displacement = float(displacement)


class BaseZone(ABC):
    """
    Abstract Base Class for all Movement Zone implementations (LineZone, PolygonZone, etc.).
    """

    def __init__(self, zone_id: str, zone_name: str, zone_type: ZoneType):
        self.zone_id = zone_id
        self.zone_name = zone_name
        self.zone_type = zone_type

    @abstractmethod
    def evaluate_trajectory(
        self,
        trajectory: List[Tuple[float, float]],
        min_crossing_distance: float = 5.0
    ) -> CrossingResult:
        """
        Evaluate a sequence of center points [p(t-N), ..., p(t)] against the zone boundary.
        """
        pass

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """
        Return metadata info describing zone geometry and configuration.
        """
        pass

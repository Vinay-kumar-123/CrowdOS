import uuid
import threading
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class GateType(str, Enum):
    """
    Gate directional classification.
    """
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    BIDIRECTIONAL = "BIDIRECTIONAL"


class GateConfig(BaseModel):
    """
    Configurable Gate entity model.
    """
    gate_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gate_name: str = Field(..., description="Human-readable gate name")
    camera_id: str = Field(..., description="Camera ID hosting this gate")
    gate_type: GateType = Field(default=GateType.BIDIRECTIONAL)
    zone_type: str = Field(default="LINE", description="LINE or POLYGON")
    zone_coordinates: List[List[float]] = Field(
        ...,
        description="Coordinates: [[x1, y1], [x2, y2]] for line or [[x,y],...] for polygon"
    )
    normal_vector: Optional[List[float]] = Field(
        default=None,
        description="Optional [dx, dy] pointing towards INSIDE / ENTRY direction"
    )
    enabled: bool = Field(default=True)
    description: str = Field(default="")
    venue_id: str = Field(default="default_venue", description="Venue identifier for multi-gate occupancy")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "gate_name": self.gate_name,
            "camera_id": self.camera_id,
            "gate_type": self.gate_type.value if isinstance(self.gate_type, GateType) else str(self.gate_type),
            "zone_type": self.zone_type,
            "zone_coordinates": self.zone_coordinates,
            "normal_vector": self.normal_vector,
            "enabled": self.enabled,
            "description": self.description,
            "venue_id": self.venue_id,
        }


class GateManager:
    """
    Thread-safe Gate Configuration Manager supporting multi-gate and multi-camera setups.
    """

    def __init__(self):
        self._gates: Dict[str, GateConfig] = {}
        self._lock = threading.Lock()

    def add_gate(self, gate: GateConfig) -> bool:
        with self._lock:
            self._gates[gate.gate_id] = gate
            return True

    def get_gate(self, gate_id: str) -> Optional[GateConfig]:
        with self._lock:
            return self._gates.get(gate_id)

    def get_gates_for_camera(self, camera_id: str) -> List[GateConfig]:
        with self._lock:
            return [g for g in self._gates.values() if g.camera_id == camera_id and g.enabled]

    def remove_gate(self, gate_id: str) -> bool:
        with self._lock:
            if gate_id in self._gates:
                del self._gates[gate_id]
                return True
            return False

    def list_gates(self) -> List[GateConfig]:
        with self._lock:
            return list(self._gates.values())

    def list_all_gates(self) -> List[GateConfig]:
        """Alias for list_gates() for API clarity."""
        return self.list_gates()

    def clear(self) -> None:
        with self._lock:
            self._gates.clear()

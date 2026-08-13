"""
Rule-based Anomaly Definitions for CrowdOS Intelligence Engine.
"""
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class AnomalyType(str, Enum):
    ENTRY_SURGE = "ENTRY_SURGE"
    EXIT_SURGE = "EXIT_SURGE"
    OCCUPANCY_SPIKE = "OCCUPANCY_SPIKE"
    MOVEMENT_STAGNATION = "MOVEMENT_STAGNATION"
    GATE_FLOW_ANOMALY = "GATE_FLOW_ANOMALY"


class AnomalySignal(BaseModel):
    """
    Internal signal emitted when an anomaly rule evaluates to True.
    """
    anomaly_type: AnomalyType
    venue_id: str = Field(default="default_venue")
    gate_id: Optional[str] = Field(default=None)
    description: str = Field(...)
    severity: str = Field(default="MEDIUM", description="INFO, LOW, MEDIUM, HIGH, CRITICAL")
    value: float = Field(default=0.0)
    threshold: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly_type": self.anomaly_type.value if isinstance(self.anomaly_type, AnomalyType) else str(self.anomaly_type),
            "venue_id": self.venue_id,
            "gate_id": self.gate_id,
            "description": self.description,
            "severity": self.severity,
            "value": round(self.value, 2),
            "threshold": round(self.threshold, 2),
            "metadata": self.metadata,
        }

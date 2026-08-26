"""
Sprint 11 — Real-Time WebSocket & Event Streaming Layer.
"""
from app.realtime.connection_manager import ConnectionManager, ws_manager
from app.realtime.broadcaster import Broadcaster, broadcaster
from app.realtime.router import realtime_router
from app.realtime.schemas import (
    WebSocketEnvelope,
    WebSocketEventType,
    OccupancyUpdatePayload,
    FlowUpdatePayload,
    IntelligenceUpdatePayload,
    AlertEventPayload,
    PredictionUpdatePayload,
    SessionUpdatePayload,
    InitialStatePayload,
    SystemStatusPayload,
)

__all__ = [
    "ConnectionManager",
    "ws_manager",
    "Broadcaster",
    "broadcaster",
    "realtime_router",
    "WebSocketEnvelope",
    "WebSocketEventType",
    "OccupancyUpdatePayload",
    "FlowUpdatePayload",
    "IntelligenceUpdatePayload",
    "AlertEventPayload",
    "PredictionUpdatePayload",
    "SessionUpdatePayload",
    "InitialStatePayload",
    "SystemStatusPayload",
]

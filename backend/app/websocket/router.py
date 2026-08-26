"""
WebSocket Router — Sprint 11.
Re-exports realtime_router from app.realtime for backward compatibility.
"""
from app.realtime.router import realtime_router as ws_router

__all__ = ["ws_router"]

"""
WebSocket Connection Manager — Sprint 11.
Re-exports ws_manager from app.realtime for backward compatibility.
"""
from app.realtime.connection_manager import ws_manager, ConnectionManager

__all__ = ["ws_manager", "ConnectionManager"]

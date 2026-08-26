"""
Sprint 11 — WebSocket Connection Manager.

Manages active WebSocket connections grouped per venue with thread-safe / asyncio-safe
connection pools, dead connection pruning, venue isolation, and resilient broadcasting.
"""
import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any, Union
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger("crowdos.realtime.connection_manager")


class ConnectionManager:
    """
    Manages active WebSocket connections partitioned by venue_id.
    """

    def __init__(self):
        # venue_id -> set of active WebSockets
        self._venue_connections: Dict[str, Set[WebSocket]] = {}
        # general/global connections (e.g. connected to /ws)
        self._global_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, venue_id: Optional[str] = None) -> None:
        """
        Accept and register a new WebSocket connection.
        """
        await websocket.accept()
        async with self._lock:
            if venue_id:
                if venue_id not in self._venue_connections:
                    self._venue_connections[venue_id] = set()
                self._venue_connections[venue_id].add(websocket)
                count = len(self._venue_connections[venue_id])
                logger.info(f"WebSocket client connected to venue '{venue_id}'. Venue clients: {count}")
            else:
                self._global_connections.add(websocket)
                logger.info(f"WebSocket client connected to global feed. Global clients: {len(self._global_connections)}")

    async def disconnect(self, websocket: WebSocket, venue_id: Optional[str] = None) -> None:
        """
        Deregister and clean up a WebSocket connection.
        """
        async with self._lock:
            self._remove_connection_locked(websocket, venue_id)

    def _remove_connection_locked(self, websocket: WebSocket, venue_id: Optional[str] = None) -> None:
        """Internal helper to remove a connection without taking the lock again."""
        if venue_id and venue_id in self._venue_connections:
            self._venue_connections[venue_id].discard(websocket)
            if not self._venue_connections[venue_id]:
                del self._venue_connections[venue_id]
            count = len(self._venue_connections.get(venue_id, set()))
            logger.info(f"WebSocket client disconnected from venue '{venue_id}'. Remaining venue clients: {count}")
        elif not venue_id:
            self._global_connections.discard(websocket)
            # Also clean up from any venue set if venue_id was unknown
            for v_id, conn_set in list(self._venue_connections.items()):
                if websocket in conn_set:
                    conn_set.discard(websocket)
                    if not conn_set:
                        del self._venue_connections[v_id]
            logger.info(f"WebSocket client disconnected. Total remaining: {self.get_total_client_count()}")

    async def broadcast_to_venue(
        self,
        venue_id: str,
        message: Union[str, Dict[str, Any], BaseModel],
    ) -> int:
        """
        Broadcast a message to all clients connected to the specified venue,
        as well as global listeners.
        Returns the number of successfully reached clients.
        Dead or failing clients are pruned automatically without breaking broadcast to others.
        """
        payload = self._serialize_message(message)
        dead_connections = []
        sent_count = 0

        # Snapshot active targets under lock to avoid holding lock during I/O
        async with self._lock:
            targets = list(self._venue_connections.get(venue_id, set())) + list(self._global_connections)

        for ws in targets:
            try:
                await ws.send_text(payload)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed sending message to WebSocket client for venue '{venue_id}': {e}")
                dead_connections.append(ws)

        # Prune dead connections if any failed
        if dead_connections:
            async with self._lock:
                for dead_ws in dead_connections:
                    self._remove_connection_locked(dead_ws, venue_id)
                    try:
                        await dead_ws.close()
                    except Exception:
                        pass

        return sent_count

    async def broadcast_to_all(
        self,
        message: Union[str, Dict[str, Any], BaseModel],
    ) -> int:
        """
        Broadcast a message across all venues and global listeners.
        """
        payload = self._serialize_message(message)
        dead_connections = []
        sent_count = 0

        async with self._lock:
            all_targets = set(self._global_connections)
            for conn_set in self._venue_connections.values():
                all_targets.update(conn_set)
            targets = list(all_targets)

        for ws in targets:
            try:
                await ws.send_text(payload)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed sending broadcast to WebSocket client: {e}")
                dead_connections.append(ws)

        if dead_connections:
            async with self._lock:
                for dead_ws in dead_connections:
                    self._remove_connection_locked(dead_ws)
                    try:
                        await dead_ws.close()
                    except Exception:
                        pass

        return sent_count

    def get_venue_client_count(self, venue_id: str) -> int:
        """Get number of connected clients for a venue."""
        return len(self._venue_connections.get(venue_id, set()))

    def get_total_client_count(self) -> int:
        """Get total number of active WebSocket connections across all venues."""
        total = len(self._global_connections)
        for s in self._venue_connections.values():
            total += len(s)
        return total

    def _serialize_message(self, message: Union[str, Dict[str, Any], BaseModel]) -> str:
        """Helper to convert dictionary, Pydantic model, or string into JSON string."""
        if isinstance(message, str):
            return message
        if hasattr(message, "model_dump_json"):
            return message.model_dump_json()
        if hasattr(message, "model_dump"):
            return json.dumps(message.model_dump())
        if isinstance(message, dict):
            return json.dumps(message)
        return json.dumps(message, default=str)


ws_manager = ConnectionManager()

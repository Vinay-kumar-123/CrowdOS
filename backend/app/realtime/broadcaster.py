"""
Sprint 11 — Real-Time Broadcaster & Event Bus.

Bridges FastAPI domain services to WebSocket clients using a dual-layer strategy:
1. In-Memory Local Broadcasting (via ConnectionManager)
2. Redis Pub/Sub Event Bus (for cross-instance horizontal scaling)

Degraded Mode:
    If Redis is offline or disconnected, automatically falls back to in-memory
    broadcasting with zero application failures or performance degradation.

Non-Blocking Guarantee:
    Broadcasting is asynchronous and exception-safe. A WebSocket client disconnect
    or Redis hiccup will NEVER fail an underlying database transaction or API request.
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, List, Union
from app.realtime.connection_manager import ws_manager, ConnectionManager
from app.realtime.schemas import (
    WebSocketEnvelope,
    WebSocketEventType,
    OccupancyUpdatePayload,
    FlowUpdatePayload,
    IntelligenceUpdatePayload,
    AlertEventPayload,
    PredictionUpdatePayload,
    SessionUpdatePayload,
    SystemStatusPayload,
    utc_iso_now,
)
from app.database.redis.connection import redis_connection

logger = logging.getLogger("crowdos.realtime.broadcaster")


class Broadcaster:
    """
    Unified real-time event dispatcher coordinating local WebSocket clients
    and Redis Pub/Sub channels.
    """

    def __init__(self, manager: ConnectionManager = ws_manager):
        self._manager = manager
        self._redis_listener_task: Optional[asyncio.Task] = None
        self._is_listening: bool = False

    # -----------------------------------------------------------------------
    # Core Dispatcher
    # -----------------------------------------------------------------------

    async def broadcast_envelope(self, envelope: WebSocketEnvelope) -> None:
        """
        Broadcast a strongly-typed WebSocketEnvelope to local clients and Redis.
        """
        try:
            venue_id = envelope.venue_id
            payload_json = envelope.model_dump_json()

            # 1. Local in-memory delivery
            if venue_id == "all" or venue_id == "*":
                await self._manager.broadcast_to_all(payload_json)
            else:
                await self._manager.broadcast_to_venue(venue_id, payload_json)

            # 2. Redis Pub/Sub delivery (if connected)
            if redis_connection.is_connected:
                client = redis_connection.get_client()
                if client:
                    channel = f"crowdos:realtime:{venue_id}"
                    try:
                        await client.publish(channel, payload_json)
                    except Exception as re:
                        logger.debug(f"Redis publish notice: {re}")

        except Exception as e:
            # Absolute resilience: Broadcaster errors must never crash caller
            logger.warning(f"Broadcaster dispatch non-fatal warning: {e}")

    # -----------------------------------------------------------------------
    # High-Level Event Helpers
    # -----------------------------------------------------------------------

    async def broadcast_occupancy_update(
        self,
        venue_id: str,
        session_id: Optional[str],
        current_occupancy: int,
        venue_capacity: int,
        occupancy_ratio: float,
        total_entries: int,
        total_exits: int,
        net_flow: int,
        gate_occupancies: Optional[Dict[str, int]] = None,
    ) -> None:
        """Broadcast live occupancy metrics update."""
        payload = OccupancyUpdatePayload(
            session_id=session_id,
            current_occupancy=current_occupancy,
            venue_capacity=venue_capacity,
            occupancy_ratio=round(occupancy_ratio, 4),
            total_entries=total_entries,
            total_exits=total_exits,
            net_flow=net_flow,
            gate_occupancies=gate_occupancies or {},
        )
        envelope = WebSocketEnvelope[OccupancyUpdatePayload](
            type=WebSocketEventType.OCCUPANCY_UPDATE,
            venue_id=venue_id,
            timestamp=utc_iso_now(),
            data=payload,
        )
        await self.broadcast_envelope(envelope)

    async def broadcast_flow_update(
        self,
        venue_id: str,
        session_id: Optional[str],
        entry_rate_1m: float,
        entry_rate_5m: float,
        exit_rate_5m: float,
        net_flow_rate_5m: float,
        busiest_gate: Optional[str] = None,
        gate_flows: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        """Broadcast live flow rate metrics update."""
        payload = FlowUpdatePayload(
            session_id=session_id,
            entry_rate_1m=round(entry_rate_1m, 2),
            entry_rate_5m=round(entry_rate_5m, 2),
            exit_rate_5m=round(exit_rate_5m, 2),
            net_flow_rate_5m=round(net_flow_rate_5m, 2),
            busiest_gate=busiest_gate,
            gate_flows=gate_flows or {},
        )
        envelope = WebSocketEnvelope[FlowUpdatePayload](
            type=WebSocketEventType.FLOW_UPDATE,
            venue_id=venue_id,
            timestamp=utc_iso_now(),
            data=payload,
        )
        await self.broadcast_envelope(envelope)

    async def broadcast_intelligence_update(
        self,
        venue_id: str,
        session_id: Optional[str],
        density_level: str,
        congestion_level: str,
        occupancy_data: OccupancyUpdatePayload,
        flow_data: FlowUpdatePayload,
    ) -> None:
        """Broadcast combined intelligence summary."""
        payload = IntelligenceUpdatePayload(
            session_id=session_id,
            density_level=density_level,
            congestion_level=congestion_level,
            occupancy=occupancy_data,
            flow=flow_data,
        )
        envelope = WebSocketEnvelope[IntelligenceUpdatePayload](
            type=WebSocketEventType.INTELLIGENCE_UPDATE,
            venue_id=venue_id,
            timestamp=utc_iso_now(),
            data=payload,
        )
        await self.broadcast_envelope(envelope)

    async def broadcast_alert_created(
        self,
        venue_id: str,
        session_id: Optional[str],
        alert_id: str,
        alert_type: str,
        severity: str,
        gate_id: Optional[str] = None,
        message: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> None:
        """Broadcast newly generated operational alert."""
        payload = AlertEventPayload(
            alert_id=alert_id,
            session_id=session_id,
            gate_id=gate_id,
            type=alert_type,
            severity=severity,
            status="ACTIVE",
            message=message,
            created_at=created_at or utc_iso_now(),
        )
        envelope = WebSocketEnvelope[AlertEventPayload](
            type=WebSocketEventType.ALERT_CREATED,
            venue_id=venue_id,
            timestamp=utc_iso_now(),
            data=payload,
        )
        await self.broadcast_envelope(envelope)

    async def broadcast_alert_resolved(
        self,
        venue_id: str,
        session_id: Optional[str],
        alert_id: str,
        alert_type: str,
        severity: str,
        gate_id: Optional[str] = None,
        message: Optional[str] = None,
        resolved_at: Optional[str] = None,
    ) -> None:
        """Broadcast resolved operational alert."""
        payload = AlertEventPayload(
            alert_id=alert_id,
            session_id=session_id,
            gate_id=gate_id,
            type=alert_type,
            severity=severity,
            status="RESOLVED",
            message=message,
            resolved_at=resolved_at or utc_iso_now(),
        )
        envelope = WebSocketEnvelope[AlertEventPayload](
            type=WebSocketEventType.ALERT_RESOLVED,
            venue_id=venue_id,
            timestamp=utc_iso_now(),
            data=payload,
        )
        await self.broadcast_envelope(envelope)

    async def broadcast_prediction_update(
        self,
        venue_id: str,
        session_id: Optional[str],
        prediction_id: Optional[str],
        risk_score: float,
        risk_level: str,
        trend_direction: str,
        trend_slope: Optional[float],
        trend_confidence: str,
        primary_recommendation: str,
        recommendations: Optional[List[str]] = None,
        factors: Optional[List[Dict[str, Any]]] = None,
        occupancy_forecast: Optional[Dict[str, Any]] = None,
        flow_forecast: Optional[Dict[str, Any]] = None,
        processing_time_ms: float = 0.0,
    ) -> None:
        """Broadcast real-time risk prediction, trend, and recommendation results."""
        payload = PredictionUpdatePayload(
            session_id=session_id,
            prediction_id=prediction_id,
            risk_score=round(risk_score, 2),
            risk_level=risk_level,
            trend_direction=trend_direction,
            trend_slope=round(trend_slope, 4) if trend_slope is not None else None,
            trend_confidence=trend_confidence,
            primary_recommendation=primary_recommendation,
            recommendations=recommendations or [primary_recommendation],
            factors=factors or [],
            occupancy_forecast=occupancy_forecast,
            flow_forecast=flow_forecast,
            processing_time_ms=processing_time_ms,
        )
        envelope = WebSocketEnvelope[PredictionUpdatePayload](
            type=WebSocketEventType.PREDICTION_UPDATE,
            venue_id=venue_id,
            timestamp=utc_iso_now(),
            data=payload,
        )
        await self.broadcast_envelope(envelope)

    async def broadcast_session_update(
        self,
        venue_id: str,
        session_id: str,
        status: str,
        action: str = "update",
        started_at: Optional[str] = None,
        stopped_at: Optional[str] = None,
        paused_at: Optional[str] = None,
        resumed_at: Optional[str] = None,
        message: Optional[str] = None,
        summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Broadcast session lifecycle transition."""
        payload = SessionUpdatePayload(
            session_id=session_id,
            status=status,
            action=action,
            started_at=started_at,
            stopped_at=stopped_at,
            paused_at=paused_at,
            resumed_at=resumed_at,
            message=message,
            summary=summary,
        )
        envelope = WebSocketEnvelope[SessionUpdatePayload](
            type=WebSocketEventType.SESSION_UPDATE,
            venue_id=venue_id,
            timestamp=utc_iso_now(),
            data=payload,
        )
        await self.broadcast_envelope(envelope)

    async def broadcast_system_status(
        self,
        status: str = "operational",
        database_connected: bool = True,
        redis_configured: bool = True,
        ai_engine_available: bool = True,
    ) -> None:
        """Broadcast global system status."""
        payload = SystemStatusPayload(
            status=status,
            database_connected=database_connected,
            redis_configured=redis_configured,
            ai_engine_available=ai_engine_available,
        )
        envelope = WebSocketEnvelope[SystemStatusPayload](
            type=WebSocketEventType.SYSTEM_STATUS,
            venue_id="all",
            timestamp=utc_iso_now(),
            data=payload,
        )
        await self.broadcast_envelope(envelope)

    # -----------------------------------------------------------------------
    # Redis Pub/Sub Background Listener Lifecycle
    # -----------------------------------------------------------------------

    async def start_redis_listener(self) -> None:
        """
        Start background listener task for Redis Pub/Sub channels if Redis is active.
        """
        if not redis_connection.is_connected:
            logger.info("Redis not connected — real-time broadcaster running in in-memory mode.")
            return

        if self._redis_listener_task is None or self._redis_listener_task.done():
            self._is_listening = True
            self._redis_listener_task = asyncio.create_task(self._redis_pubsub_loop())
            logger.info("Real-time Redis Pub/Sub listener started.")

    async def stop_redis_listener(self) -> None:
        """
        Stop background Redis Pub/Sub listener task.
        """
        self._is_listening = False
        if self._redis_listener_task and not self._redis_listener_task.done():
            self._redis_listener_task.cancel()
            try:
                await self._redis_listener_task
            except asyncio.CancelledError:
                pass
            self._redis_listener_task = None
            logger.info("Real-time Redis Pub/Sub listener stopped cleanly.")

    async def _redis_pubsub_loop(self) -> None:
        """Background loop reading from Redis Pub/Sub and fanning out to local WebSockets."""
        client = redis_connection.get_client()
        if not client:
            return

        try:
            pubsub = client.pubsub()
            await pubsub.psubscribe("crowdos:realtime:*")
            logger.info("Subscribed to Redis pattern 'crowdos:realtime:*'")

            while self._is_listening:
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message and message.get("type") == "pmessage":
                        channel = message.get("channel", "")
                        data_str = message.get("data", "")
                        if channel and data_str:
                            # Extract venue_id from channel crowdos:realtime:{venue_id}
                            venue_id = channel.split(":")[-1]
                            if venue_id == "all":
                                await self._manager.broadcast_to_all(data_str)
                            else:
                                await self._manager.broadcast_to_venue(venue_id, data_str)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"Redis PubSub read tick notice: {e}")
                    await asyncio.sleep(1.0)

            await pubsub.punsubscribe("crowdos:realtime:*")
            await pubsub.close()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Redis Pub/Sub listener encountered error: {e}")


broadcaster = Broadcaster()

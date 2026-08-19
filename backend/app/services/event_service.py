"""
Event Ingest Service — Sprint 9.

Receives external movement event payloads (ENTRY/EXIT) and routes them through
Sprint 6 Movement Engine data contracts into Sprint 7 EventIntelligenceEngine.

Traceable Execution Path:
    API (POST /api/v1/venues/{venue_id}/sessions/{session_id}/events)
      ↓
    EventService.ingest_event()
      ↓
    VenueEngineRegistry (Adapter managing MovementEngine, IntelligenceEngine, PredictionEngine)
      ↓
    Sprint 6 Movement Engine (EntryEvent / ExitEvent + OccupancyTracker)
      ↓
    Sprint 7 EventIntelligenceEngine.process_event(entry_or_exit_event)
      ↓
    Sprint 7 EventIntelligenceEngine.process_occupancy_state(occupancy_state)

Zero duplicate business intelligence calculations.
Privacy guarantee: No face embeddings, raw video frames, or biometric vectors.
"""
import logging
import uuid
from datetime import datetime, timezone
from app.services.ai_engine_adapter import VenueEngineRegistry, VenueEngines
from app.schemas.events import EventIngestRequest, EventIngestResponse
from app.core.exceptions import NotFoundException, CrowdOSException, EngineUnavailableException

logger = logging.getLogger("crowdos.event_service")


class EventService:
    """
    Event ingest service — bridges REST layer to Sprint 6 Movement & Sprint 7 Intelligence Engines.
    """

    def __init__(self, registry: VenueEngineRegistry):
        self._registry = registry

    def _get_engines(self, venue_id: str) -> VenueEngines:
        engines = self._registry.get(venue_id)
        if engines is None:
            raise NotFoundException(f"Venue '{venue_id}' not initialized. Create a session first.")
        return engines

    def ingest_event(
        self,
        venue_id: str,
        session_id: str,
        request: EventIngestRequest,
    ) -> EventIngestResponse:
        """
        Ingest a movement event (ENTRY or EXIT).

        1. Validates session existence in Sprint 7 SessionManager.
        2. Instantiates authoritative Sprint 6 EntryEvent / ExitEvent payload.
        3. Updates Sprint 6 OccupancyTracker.
        4. Ingests event into Sprint 7 EventIntelligenceEngine.process_event().
        5. Synchronizes Sprint 6 OccupancyState into Sprint 7.
        """
        engines = self._get_engines(venue_id)

        # Validate event_type
        event_type = request.event_type.upper()
        if event_type not in ("ENTRY", "EXIT"):
            raise CrowdOSException(
                detail=f"Invalid event_type '{request.event_type}'. Must be 'ENTRY' or 'EXIT'.",
                status_code=422,
            )

        # Confirm session exists in Sprint 7 SessionManager
        session = engines.intelligence.session_manager.get_session(session_id)
        if session is None:
            raise NotFoundException(f"Session '{session_id}' not found for venue '{venue_id}'.")

        timestamp = request.timestamp or datetime.now(timezone.utc).isoformat()
        event_id = request.event_id or str(uuid.uuid4())
        camera_id = getattr(request, "camera_id", None) or f"cam_{request.gate_id}"
        track_id = getattr(request, "track_id", None) or f"trk_{event_id[:8]}"
        detection_id = getattr(request, "detection_id", None) or str(uuid.uuid4())

        # Construct official Sprint 6 Event
        try:
            from movement.events.schema import EntryEvent, ExitEvent, EventSource

            if event_type == "ENTRY":
                event = EntryEvent(
                    camera_id=camera_id,
                    gate_id=request.gate_id,
                    entry_gate_id=request.gate_id,
                    track_id=track_id,
                    detection_id=detection_id,
                    timestamp=timestamp,
                    entry_timestamp=timestamp,
                    event_id=event_id,
                    direction="ENTRY",
                    event_source=EventSource.TRACK_CROSSING,
                )
                if hasattr(engines.movement, "occupancy_tracker"):
                    engines.movement.occupancy_tracker.record_entry(camera_id, request.gate_id)
            else: # EXIT
                event = ExitEvent(
                    camera_id=camera_id,
                    gate_id=request.gate_id,
                    exit_gate_id=request.gate_id,
                    track_id=track_id,
                    detection_id=detection_id,
                    timestamp=timestamp,
                    exit_timestamp=timestamp,
                    event_id=event_id,
                    direction="EXIT",
                    dwell_time=request.dwell_time,
                    event_source=EventSource.TRACK_CROSSING,
                )
                if hasattr(engines.movement, "occupancy_tracker"):
                    engines.movement.occupancy_tracker.record_exit(camera_id, request.gate_id)
        except ImportError:
            # Fallback for stub mode when running in test environments without ai-engine on path
            event = type("StubEvent", (), {
                "event_type": type("T", (), {"value": event_type})(),
                "gate_id": request.gate_id,
                "timestamp": timestamp,
                "event_id": event_id,
                "dwell_time": request.dwell_time,
            })()

        # Route event into Sprint 7 EventIntelligenceEngine
        try:
            result = engines.intelligence.process_event(event)
        except Exception as e:
            logger.error(f"process_event() failed for venue {venue_id}: {e}")
            return EventIngestResponse(
                status="error",
                event_type=event_type,
                gate_id=request.gate_id,
                reason=str(e),
                alerts_generated=0,
                processing_time_ms=0.0,
            )

        # Synchronize Sprint 6 OccupancyState into Sprint 7 if movement engine is active
        try:
            if hasattr(engines.movement, "get_occupancy"):
                occ_state = engines.movement.get_occupancy()
                if occ_state:
                    engines.intelligence.process_occupancy_state(occ_state)
        except Exception as occ_err:
            logger.debug(f"Occupancy sync debug: {occ_err}")

        return EventIngestResponse(
            status=result.get("status", "processed"),
            event_type=result.get("event_type", event_type),
            gate_id=result.get("gate_id", request.gate_id),
            reason=result.get("reason"),
            alerts_generated=result.get("alerts_generated", 0),
            processing_time_ms=result.get("processing_time_ms", 0.0),
        )

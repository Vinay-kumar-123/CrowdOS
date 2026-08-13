import time
import threading
from typing import List, Dict, Optional, Tuple, Any

from tracking.results.schema import TrackingResult, TrackState, TrackedPerson
from recognition.results.schema import RecognitionResult, RecognizedPerson
from movement.config.gate_config import GateConfig, GateType, GateManager
from movement.config.settings import movement_settings
from movement.zones.base_zone import BaseZone, CrossingDirection
from movement.zones.line_zone import LineZone
from movement.zones.polygon_zone import PolygonZone
from movement.state.movement_state import MovementState
from movement.state.state_manager import MovementStateManager
from movement.state.occupancy import OccupancyTracker, OccupancyState
from movement.state.journey import JourneyTracker, Journey
from movement.events.schema import (
    MovementEvent, EntryEvent, ExitEvent, MovementEventType, EventSource
)
from movement.events.deduplicator import EventDeduplicator
from movement.events.validator import MovementEventValidator
from movement.engine.metrics import MovementMetricsTracker
from movement.utils.logger import movement_logger


class MovementEngine:
    """
    Enterprise Multi-Camera Gate, Entry/Exit & Movement Intelligence Engine.

    Architecture & Invariants:
    - Consumes TrackingResult (Sprint 4) + RecognitionResult (Sprint 5) + Gate Configuration.
    - Physical movement is 100% driven by tracking geometry. Missing face / UNKNOWN identity never blocks movement events.
    - Scoped strictly by camera_id + gate_id + track_id.
    - Multi-level in-memory occupancy tracker (non-negative bounds).
    - In-memory active journey tracking with multi-visit support and safe orphan exit handling.
    - Deduplication of duplicate crossing events within sliding window.
    - Thread-safe across concurrent multi-camera streams.
    """

    def __init__(
        self,
        gate_manager: Optional[GateManager] = None,
        occupancy_tracker: Optional[OccupancyTracker] = None,
        journey_tracker: Optional[JourneyTracker] = None,
        deduplicator: Optional[EventDeduplicator] = None,
        validator: Optional[MovementEventValidator] = None
    ):
        self.gate_manager = gate_manager or GateManager()
        self.occupancy_tracker = occupancy_tracker or OccupancyTracker()
        self.journey_tracker = journey_tracker or JourneyTracker()
        self.deduplicator = deduplicator or EventDeduplicator()
        self.validator = validator or MovementEventValidator()

        self.state_manager = MovementStateManager(
            trajectory_window=movement_settings.TRAJECTORY_WINDOW,
            max_lost_frames=movement_settings.MAX_TRACK_LOST_FRAMES
        )
        self.metrics = MovementMetricsTracker()
        self._zone_cache: Dict[str, BaseZone] = {}
        self._lock = threading.Lock()

        movement_logger.info("MovementEngine initialized successfully")

    def _get_or_build_zone(self, gate: GateConfig) -> BaseZone:
        with self._lock:
            if gate.gate_id in self._zone_cache:
                return self._zone_cache[gate.gate_id]

            if gate.zone_type.upper() == "POLYGON" or len(gate.zone_coordinates) > 2:
                pts = [(float(p[0]), float(p[1])) for p in gate.zone_coordinates]
                zone = PolygonZone(
                    zone_id=gate.gate_id,
                    zone_name=gate.gate_name,
                    polygon_points=pts
                )
            else:
                p1 = (float(gate.zone_coordinates[0][0]), float(gate.zone_coordinates[0][1]))
                p2 = (float(gate.zone_coordinates[1][0]), float(gate.zone_coordinates[1][1]))
                norm = tuple(gate.normal_vector) if gate.normal_vector else None
                zone = LineZone(
                    zone_id=gate.gate_id,
                    zone_name=gate.gate_name,
                    line_start=p1,
                    line_end=p2,
                    normal_vector=norm
                )

            self._zone_cache[gate.gate_id] = zone
            return zone

    def process_frame(
        self,
        tracking_result: TrackingResult,
        recognition_result: Optional[RecognitionResult] = None
    ) -> List[MovementEvent]:
        """
        Process single frame tracking + recognition inputs and generate validated movement events.
        """
        start_time = time.perf_counter()
        camera_id = tracking_result.camera_id
        frame_number = tracking_result.frame_number
        timestamp = tracking_result.timestamp

        # Index recognition results by track_id for fast lookup
        rec_map: Dict[str, RecognizedPerson] = {}
        if recognition_result and recognition_result.recognized_persons:
            for rec in recognition_result.recognized_persons:
                rec_map[rec.track_id] = rec

        # Get active gates for this camera
        active_gates = self.gate_manager.get_gates_for_camera(camera_id)
        if not active_gates:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.metrics.record_frame(
                tracks_processed=len(tracking_result.tracks),
                events_generated=0, entries=0, exits=0, rejected=0, duplicates=0,
                processing_time_ms=elapsed_ms
            )
            return []

        active_tracks = [
            t for t in tracking_result.tracks
            if t.track_state in (TrackState.ACTIVE, TrackState.REIDENTIFIED, TrackState.NEW)
        ]
        active_track_ids = [t.track_id for t in active_tracks]

        generated_events: List[MovementEvent] = []
        entries_count = 0
        exits_count = 0
        rejected_count = 0
        duplicate_count = 0

        for gate in active_gates:
            zone = self._get_or_build_zone(gate)

            for track in active_tracks:
                track_id = track.track_id
                rec_info = rec_map.get(track_id)

                identity_id = rec_info.identity_id if rec_info else "UNKNOWN"
                identity_status = rec_info.identity_status.value if (rec_info and hasattr(rec_info.identity_status, "value")) else "UNKNOWN"
                face_id = rec_info.face_id if rec_info else ""

                # Get state machine for track
                state = self.state_manager.get_or_create_state(camera_id, gate.gate_id, track_id)
                state.update_position(
                    center=track.center,
                    frame_number=frame_number,
                    identity_id=identity_id,
                    identity_status=identity_status
                )

                # Evaluate crossing trajectory
                crossing_res = zone.evaluate_trajectory(
                    trajectory=state.get_trajectory_list(),
                    min_crossing_distance=movement_settings.MIN_CROSSING_DISTANCE
                )

                if crossing_res.has_crossed:
                    x_dir = crossing_res.direction

                    # Map zone crossing direction to MovementEventType based on GateType configuration
                    event_type: Optional[MovementEventType] = None
                    if x_dir == CrossingDirection.ENTRY:
                        if gate.gate_type in (GateType.ENTRY, GateType.BIDIRECTIONAL):
                            event_type = MovementEventType.ENTRY
                    elif x_dir == CrossingDirection.EXIT:
                        if gate.gate_type in (GateType.EXIT, GateType.BIDIRECTIONAL):
                            event_type = MovementEventType.EXIT

                    if event_type is None:
                        rejected_count += 1
                        continue

                    # Check deduplication
                    if self.deduplicator.is_duplicate(
                        camera_id=camera_id,
                        gate_id=gate.gate_id,
                        track_id=track_id,
                        event_type=event_type.value,
                        identity_id=identity_id
                    ):
                        duplicate_count += 1
                        continue

                    # Construct specialized Event object
                    if event_type == MovementEventType.ENTRY:
                        event = EntryEvent(
                            camera_id=camera_id,
                            gate_id=gate.gate_id,
                            entry_gate_id=gate.gate_id,
                            track_id=track_id,
                            detection_id=track.detection_id,
                            face_id=face_id,
                            identity_id=identity_id,
                            identity_status=identity_status,
                            timestamp=timestamp,
                            entry_timestamp=timestamp,
                            bounding_box=track.bbox,
                            direction="ENTRY",
                            confidence=crossing_res.confidence,
                            event_source=EventSource.TRACK_CROSSING
                        )
                    else: # EXIT
                        event = ExitEvent(
                            camera_id=camera_id,
                            gate_id=gate.gate_id,
                            exit_gate_id=gate.gate_id,
                            track_id=track_id,
                            detection_id=track.detection_id,
                            face_id=face_id,
                            identity_id=identity_id,
                            identity_status=identity_status,
                            timestamp=timestamp,
                            exit_timestamp=timestamp,
                            bounding_box=track.bbox,
                            direction="EXIT",
                            confidence=crossing_res.confidence,
                            event_source=EventSource.TRACK_CROSSING
                        )

                    # Validate event payload
                    is_valid, errs = self.validator.validate_event(event)
                    if not is_valid:
                        movement_logger.warning(f"Rejected invalid movement event: {errs}")
                        rejected_count += 1
                        continue

                    # Record deduplication lock
                    self.deduplicator.record_event(
                        camera_id=camera_id,
                        gate_id=gate.gate_id,
                        track_id=track_id,
                        event_type=event_type.value,
                        identity_id=identity_id
                    )

                    # Update State Machine, Occupancy, and Journey
                    if event_type == MovementEventType.ENTRY:
                        state.transition_to(MovementState.ENTERED)
                        state.entry_frame = frame_number
                        state.entry_time = time.time()

                        self.occupancy_tracker.record_entry(camera_id, gate.gate_id)
                        journey = self.journey_tracker.start_journey(
                            camera_id=camera_id,
                            track_id=track_id,
                            gate_id=gate.gate_id,
                            identity_id=identity_id,
                            identity_status=identity_status,
                            timestamp=timestamp,
                            event_payload=event.to_dict()
                        )
                        event.journey_id = journey.journey_id
                        entries_count += 1

                    elif event_type == MovementEventType.EXIT:
                        state.transition_to(MovementState.EXITED)
                        state.exit_frame = frame_number
                        state.exit_time = time.time()

                        self.occupancy_tracker.record_exit(camera_id, gate.gate_id)
                        journey = self.journey_tracker.complete_journey(
                            camera_id=camera_id,
                            track_id=track_id,
                            gate_id=gate.gate_id,
                            identity_id=identity_id,
                            timestamp=timestamp,
                            event_payload=event.to_dict()
                        )
                        if journey:
                            event.journey_id = journey.journey_id
                            if isinstance(event, ExitEvent):
                                event.dwell_time = journey.dwell_time
                        exits_count += 1

                    generated_events.append(event)

            # Cleanup expired/missing tracks for this camera & gate
            self.state_manager.mark_missing_tracks(camera_id, gate.gate_id, active_track_ids)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self.metrics.record_frame(
            tracks_processed=len(active_tracks),
            events_generated=len(generated_events),
            entries=entries_count,
            exits=exits_count,
            rejected=rejected_count,
            duplicates=duplicate_count,
            processing_time_ms=elapsed_ms
        )

        return generated_events


    def get_occupancy(self) -> OccupancyState:
        active_j_count = self.journey_tracker.get_active_journeys_count()
        return self.occupancy_tracker.get_state(active_journeys_count=active_j_count)

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "metrics": self.metrics.get_metrics(),
            "occupancy": self.get_occupancy().to_dict(),
            "active_journeys": self.journey_tracker.get_active_journeys_count(),
            "completed_journeys": len(self.journey_tracker.list_completed_journeys())
        }

    def reset_all(self) -> None:
        self.state_manager.clear()
        self.occupancy_tracker.reset()
        self.journey_tracker.clear()
        self.deduplicator.clear()
        self.metrics.reset()
        with self._lock:
            self._zone_cache.clear()

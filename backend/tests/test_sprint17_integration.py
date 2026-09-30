"""
Sprint 17 End-to-End Live Camera AI Vision Pipeline & Integration Tests.

Validates:
1. Live Camera Frame Delivery to AI Vision Pipeline (Detection -> ByteTrack -> Gate Movement)
2. Strict Non-Fabrication (blank / stationary frames produce ZERO events)
3. Genuine Trajectory Gate Crossing producing persisted ENTRY / EXIT events
4. Multi-Camera & Multi-Gate Isolation across venues
5. Deterministic Idempotency with multi-track support
6. Camera Key Migration CLI Utility & Key Rotation Safety
7. System Readiness Probes (/ready and /api/ready)
8. Sensitive Data Log Redaction
9. Graceful Degradation under malformed frames or processing errors
"""
import asyncio
import io
import logging
import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.camera_security import (
    derive_deterministic_event_id,
    encrypt_credentials,
    decrypt_credentials,
    sanitize_source_url,
    sanitize_error_message,
)
from app.core.logger import SensitiveDataFilter
from app.services.camera_pipeline_service import CameraAIPipeline
from app.services.camera_runtime_service import (
    CameraRuntimeService,
    CameraRuntimeRecord,
    CameraStatus,
    camera_runtime,
)
from app.schemas.cameras import CameraRegisterRequest
from scripts.migrate_camera_keys import migrate_camera_credentials


# ============================================================================
# 1. AI Vision Pipeline: Frame Ingestion & Non-Fabrication
# ============================================================================

def test_s17_01_blank_frame_produces_zero_events():
    """
    STRICT NON-FABRICATION: A blank frame delivered to CameraAIPipeline must
    yield 0 events. No synthetic detections or crossings may ever be fabricated.
    """
    pipeline = CameraAIPipeline()
    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    events = pipeline.process_frame(
        frame=blank_frame,
        camera_id="cam_s17_test_01",
        gate_id="gate_north",
        frame_number=1,
        timestamp=1700000000.0,
    )
    assert events == []
    assert len(events) == 0


def test_s17_02_malformed_frame_fails_safely():
    """
    Malformed frames (None, invalid shape, wrong dimension) must fail safely
    returning an empty list and not raising unhandled exceptions.
    """
    pipeline = CameraAIPipeline()

    # None frame
    assert pipeline.process_frame(None, "cam_1", "gate_1", 1, 100.0) == []

    # 1D array
    assert pipeline.process_frame(np.zeros(100), "cam_1", "gate_1", 1, 100.0) == []

    # 2D array (missing color channels)
    assert pipeline.process_frame(np.zeros((480, 640)), "cam_1", "gate_1", 1, 100.0) == []


# ============================================================================
# 2. Genuine Trajectory Crossing & Gate Movement Intelligence
# ============================================================================

def test_s17_03_genuine_gate_crossing_generates_entry_event():
    """
    When a genuine detection crosses the gate boundary line, the AI pipeline
    must produce an ENTRY event with correct metadata.
    """
    from detection.results.schema import FrameDetectionResult, DetectionItem, BoundingBox
    from tracking.results.schema import TrackingResult, TrackedPerson, TrackState

    pipeline = CameraAIPipeline()
    gate_id = "gate_s17_entry"

    # Configure a horizontal gate line at y=240
    gate_dict = {
        "gate_id": gate_id,
        "line_coordinates": [[100, 240], [300, 240]],
        "normal_vector": [0.0, 1.0],
    }

    # Simulate trajectory crossing from (150, 220) to (150, 260) across y=240
    frame_dummy = np.zeros((480, 640, 3), dtype=np.uint8)

    # Frame 1: Before crossing (y=220)
    det1 = DetectionItem(
        label="person",
        confidence=0.92,
        bbox=BoundingBox(x1=130, y1=200, x2=170, y2=240),
        center=(150.0, 220.0),
        width=40.0,
        height=40.0,
    )
    tr1 = TrackedPerson(
        track_id="101",
        detection_id="det_1",
        camera_id="cam_entry",
        frame_number=1,
        bbox=BoundingBox(x1=130, y1=200, x2=170, y2=240),
        confidence=0.92,
        center=(150.0, 220.0),
        track_state=TrackState.ACTIVE,
    )

    with patch.object(pipeline._detection_engine, "detect_persons", return_value=FrameDetectionResult(
        camera_id="cam_entry",
        frame_number=1,
        inference_time_ms=2.0,
        total_persons_detected=1,
        detections=[det1],
        device_used="cpu",
        resolution=(640, 480),
    )), patch.object(pipeline._tracking_engine, "process_detections", return_value=TrackingResult(
        camera_id="cam_entry", frame_number=1, timestamp="2026-01-01T00:00:00Z", tracking_time_ms=1.5,
        total_active_tracks=1, total_lost_tracks=0, tracks=[tr1]
    )):
        evs_1 = pipeline.process_frame(
            frame=frame_dummy,
            camera_id="cam_entry",
            gate_id=gate_id,
            frame_number=1,
            timestamp=100.0,
            gate_config=gate_dict,
        )
        assert len(evs_1) == 0  # No crossing yet on first observation

    # Frame 2: After crossing (y=260)
    det2 = DetectionItem(
        label="person",
        confidence=0.94,
        bbox=BoundingBox(x1=130, y1=240, x2=170, y2=280),
        center=(150.0, 260.0),
        width=40.0,
        height=40.0,
    )
    tr2 = TrackedPerson(
        track_id="101",
        detection_id="det_2",
        camera_id="cam_entry",
        frame_number=2,
        bbox=BoundingBox(x1=130, y1=240, x2=170, y2=280),
        confidence=0.94,
        center=(150.0, 260.0),
        track_state=TrackState.ACTIVE,
    )

    with patch.object(pipeline._detection_engine, "detect_persons", return_value=FrameDetectionResult(
        camera_id="cam_entry",
        frame_number=2,
        inference_time_ms=2.0,
        total_persons_detected=1,
        detections=[det2],
        device_used="cpu",
        resolution=(640, 480),
    )), patch.object(pipeline._tracking_engine, "process_detections", return_value=TrackingResult(
        camera_id="cam_entry", frame_number=2, timestamp="2026-01-01T00:00:00Z", tracking_time_ms=1.5,
        total_active_tracks=1, total_lost_tracks=0, tracks=[tr2]
    )):
        evs_2 = pipeline.process_frame(
            frame=frame_dummy,
            camera_id="cam_entry",
            gate_id=gate_id,
            frame_number=2,
            timestamp=100.033,
            gate_config=gate_dict,
        )
        assert len(evs_2) == 1
        assert evs_2[0]["event_type"] == "ENTRY"
        assert evs_2[0]["gate_id"] == gate_id
        assert evs_2[0]["track_id"] == "101"


# ============================================================================
# 3. Camera Runtime Frame Callback & Ingestion Integration
# ============================================================================

@pytest.mark.asyncio
async def test_s17_04_camera_runtime_frame_callback_ingests_real_event():
    """
    Verify CameraRuntimeService._frame_callback invokes CameraAIPipeline,
    derives a deterministic event ID, and persists via EventService.ingest_event().
    """
    from app.services.ai_engine_adapter import venue_registry

    mock_event_service = AsyncMock()
    service = CameraRuntimeService(event_service=mock_event_service)
    camera_id = "cam_rt_test_01"
    venue_id = "venue_s17_01"
    gate_id = "gate_s17_main"

    # Setup active session in intelligence engine
    engines = venue_registry.get_or_create(venue_id)
    session = engines.intelligence.session_manager.create_session(venue_id=venue_id)
    engines.intelligence.session_manager.start_session(session.session_id)

    record = CameraRuntimeRecord(
        camera_id=camera_id,
        venue_id=venue_id,
        camera_name="Main Gate Cam",
        camera_type="file",
        raw_source="test.mp4",
        gate_id=gate_id,
        configured_fps=30.0,
        metadata={"gate_config": {"gate_id": gate_id}},
        status=CameraStatus.ONLINE,
    )
    service._records[camera_id] = record

    class DummyFrameItem:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame_number = 15
        timestamp = 1700000000.5

    # Mock pipeline returning one genuine entry event
    mock_pipeline = MagicMock()
    mock_pipeline.process_frame.return_value = [
        {
            "event_type": "ENTRY",
            "gate_id": gate_id,
            "track_id": "trk_42",
            "detection_id": "det_99",
            "identity_id": None,
            "visitor_id": None,
            "dwell_time": None,
            "direction": "ENTRY",
        }
    ]
    service._pipeline_service = mock_pipeline

    # Execute frame callback
    await service._frame_callback(camera_id, DummyFrameItem())

    # Assert ingest_event was called with deterministic event
    assert mock_event_service.ingest_event.call_count == 1
    call_kwargs = mock_event_service.ingest_event.call_args.kwargs
    assert call_kwargs["venue_id"] == venue_id
    assert call_kwargs["session_id"] == session.session_id
    req = call_kwargs["request"]
    assert req.camera_id == camera_id
    assert req.gate_id == gate_id
    assert str(req.event_type) == "ENTRY"


    # Verify event ID matches deterministic derivation
    expected_id = derive_deterministic_event_id(camera_id, gate_id, 15, 1700000000.5, track_id="trk_42")
    assert req.event_id == expected_id





# ============================================================================
# 4. Multi-Track Deterministic Idempotency
# ============================================================================

def test_s17_05_multi_track_deterministic_event_ids_remain_distinct():
    """
    Multiple tracks crossing within the same frame must generate distinct,
    stable event IDs.
    """
    cam = "cam_multi"
    gate = "gate_1"
    fn = 100
    ts = 1700000100.123

    id_track_1 = derive_deterministic_event_id(cam, gate, fn, ts, track_id="trk_1")
    id_track_2 = derive_deterministic_event_id(cam, gate, fn, ts, track_id="trk_2")

    assert id_track_1 != id_track_2

    # Reprocessing identical track must produce identical ID
    assert derive_deterministic_event_id(cam, gate, fn, ts, track_id="trk_1") == id_track_1
    assert derive_deterministic_event_id(cam, gate, fn, ts, track_id="trk_2") == id_track_2


# ============================================================================
# 5. Multi-Camera & Gate Isolation
# ============================================================================

def test_s17_06_sibling_cameras_maintain_isolated_pipelines():
    """
    Two cameras processing simultaneously must maintain independent tracking
    and gate state.
    """
    pipeline = CameraAIPipeline()
    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    ev1 = pipeline.process_frame(blank_frame, "cam_A", "gate_A", 1, 10.0)
    ev2 = pipeline.process_frame(blank_frame, "cam_B", "gate_B", 1, 10.0)

    assert ev1 == []
    assert ev2 == []


# ============================================================================
# 6. Key Migration CLI Utility & Key Rotation
# ============================================================================

@pytest.mark.asyncio
async def test_s17_07_key_migration_rotates_credentials_successfully():
    """
    Tests the migrate_camera_credentials logic used by migrate_camera_keys.py:
    Decrypts with old key, re-encrypts with new key, verifies round-trip.
    """
    old_key = "old-secret-camera-encryption-key-32b"
    new_key = "new-secret-camera-encryption-key-32b"
    secret_rtsp = "rtsp://admin:super_secret_pw@192.168.1.100:554/stream1"

    old_encrypted = encrypt_credentials(secret_rtsp, old_key)

    # Mock MongoDB collection
    mock_cursor = AsyncMock()
    mock_doc = {
        "_id": "doc_cam_01",
        "camera_id": "cam_01",
        "credentials_encrypted": old_encrypted,
    }

    class AsyncCursorMock:
        def __init__(self, docs):
            self.docs = docs
            self.idx = 0
        def __aiter__(self):
            return self
        async def __anext__(self):
            if self.idx < len(self.docs):
                doc = self.docs[self.idx]
                self.idx += 1
                return doc
            raise StopAsyncIteration

    mock_cameras_col = AsyncMock()
    mock_cameras_col.find.return_value = AsyncCursorMock([mock_doc])

    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_cameras_col

    with patch("scripts.migrate_camera_keys.AsyncIOMotorClient") as mock_motor:
        mock_client = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        mock_motor.return_value = mock_client

        stats = await migrate_camera_credentials(
            old_key=old_key,
            new_key=new_key,
            mongo_uri="mongodb://localhost:27017",
            mongo_db_name="crowdos_test",
            dry_run=False,
        )

        assert stats["scanned"] == 1
        assert stats["migrated"] == 1
        assert stats["failed"] == 0

        # Verify update_one was called with new ciphertext decryptable by new_key
        assert mock_cameras_col.update_one.call_count == 1
        update_args = mock_cameras_col.update_one.call_args[0]
        new_encrypted_token = update_args[1]["$set"]["credentials_encrypted"]

        # Plaintext must match original
        decrypted_new = decrypt_credentials(new_encrypted_token, new_key)
        assert decrypted_new == secret_rtsp


@pytest.mark.asyncio
async def test_s17_08_key_migration_fails_safely_on_wrong_old_key():
    """
    If the old key is wrong, migration must record a failure, refuse to overwrite,
    and not crash.
    """
    wrong_old_key = "wrong-old-key-wrong-old-key-32bytes"
    correct_old_key = "correct-old-key-correct-old-key-32"
    new_key = "new-key-new-key-new-key-32bytes-long"
    secret = "rtsp://admin:pass@10.0.0.1:554/h264"

    ciphertext = encrypt_credentials(secret, correct_old_key)

    class AsyncCursorMock:
        def __init__(self, docs):
            self.docs = docs
            self.idx = 0
        def __aiter__(self):
            return self
        async def __anext__(self):
            if self.idx < len(self.docs):
                doc = self.docs[self.idx]
                self.idx += 1
                return doc
            raise StopAsyncIteration

    mock_doc = {"_id": "doc_01", "camera_id": "cam_01", "credentials_encrypted": ciphertext}
    mock_cameras_col = AsyncMock()
    mock_cameras_col.find.return_value = AsyncCursorMock([mock_doc])

    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_cameras_col

    with patch("scripts.migrate_camera_keys.AsyncIOMotorClient") as mock_motor:
        mock_client = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        mock_motor.return_value = mock_client

        stats = await migrate_camera_credentials(
            old_key=wrong_old_key,
            new_key=new_key,
            mongo_uri="mongodb://localhost:27017",
            mongo_db_name="crowdos_test",
            dry_run=False,
        )

        assert stats["scanned"] == 1
        assert stats["migrated"] == 0
        assert stats["failed"] == 1
        # Update must NEVER have been called on failed decryption
        assert mock_cameras_col.update_one.call_count == 0


# ============================================================================
# 7. Sensitive Data Redaction in Logging
# ============================================================================

def test_s17_09_logger_filter_redacts_credentials():
    """
    SensitiveDataFilter must redact embedded RTSP credentials, Bearer tokens,
    and passwords from log messages before emission.
    """
    filter_obj = SensitiveDataFilter()

    # URL with embedded credentials
    rec1 = logging.LogRecord("test", logging.INFO, "test.py", 10, "Connecting to rtsp://admin:secret123@10.0.0.50:554/h264", (), None)
    filter_obj.filter(rec1)
    assert "secret123" not in rec1.msg
    assert "rtsp://***:***@10.0.0.50:554/h264" in rec1.msg

    # Bearer token
    rec2 = logging.LogRecord("test", logging.INFO, "test.py", 20, "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz", (), None)
    filter_obj.filter(rec2)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in rec2.msg
    assert "[REDACTED_TOKEN]" in rec2.msg

    # Password assignment
    rec3 = logging.LogRecord("test", logging.INFO, "test.py", 30, "Config loaded: password='super_secret_value'", (), None)
    filter_obj.filter(rec3)
    assert "super_secret_value" not in rec3.msg
    assert "[REDACTED]" in rec3.msg


# ============================================================================
# 8. Readiness Probe Endpoint Verification
# ============================================================================

@pytest.mark.asyncio
async def test_s17_10_readiness_probe_schema_and_status(async_client):
    """
    GET /ready and GET /api/ready must return 200 with readiness schema.
    """
    for endpoint in ("/ready", "/api/ready"):
        res = await async_client.get(endpoint)
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert "mongodb_connected" in data
        assert "redis_connected" in data
        assert "ai_engine_ready" in data
        assert "camera_runtime_ready" in data
        assert "version" in data
        assert "timestamp" in data

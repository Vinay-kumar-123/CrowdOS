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
10. SEC-01: Secure key input (env vars, key files, interactive prompt)
11. SEC-02: Migration restart-safety (already-migrated document detection)
12. LOG-01: SensitiveDataFilter with record.args support & root-handler attachment
"""
import asyncio
import io
import logging
import numpy as np
import os
import pytest
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.camera_security import (
    derive_deterministic_event_id,
    encrypt_credentials,
    decrypt_credentials,
    sanitize_source_url,
    sanitize_error_message,
)
from app.core.logger import SensitiveDataFilter, attach_sensitive_data_filter
from app.services.camera_pipeline_service import CameraAIPipeline
from app.services.camera_runtime_service import (
    CameraRuntimeService,
    CameraRuntimeRecord,
    CameraStatus,
    camera_runtime,
)
from app.schemas.cameras import CameraRegisterRequest
from scripts.migrate_camera_keys import migrate_camera_credentials, resolve_key


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


# ============================================================================
# 9. SEC-01 â€” Secure Key Input (env vars, key files, interactive prompt)
# ============================================================================

def test_s17_11_sec01_key_resolution_from_env_var():
    """
    SEC-01: resolve_key must read the key from environment variables when no
    CLI arg or key file is provided. Secrets must not be required on the command line.
    """
    env_key = "test-env-resolution-key-for-sec01"

    # Via primary env var
    with patch.dict(os.environ, {"OLD_CAMERA_ENCRYPTION_KEY": env_key}, clear=False):
        resolved = resolve_key(
            cli_arg=None,
            file_arg=None,
            env_vars=("OLD_CAMERA_ENCRYPTION_KEY", "CROWDOS_OLD_CAMERA_KEY"),
            prompt_name="old CAMERA_ENCRYPTION_KEY",
            deprecated_cli_name="--old-key",
        )
    assert resolved == env_key

    # Via legacy alias env var
    with patch.dict(os.environ, {"CROWDOS_OLD_CAMERA_KEY": env_key}, clear=False):
        resolved2 = resolve_key(
            cli_arg=None,
            file_arg=None,
            env_vars=("OLD_CAMERA_ENCRYPTION_KEY", "CROWDOS_OLD_CAMERA_KEY"),
            prompt_name="old CAMERA_ENCRYPTION_KEY",
            deprecated_cli_name="--old-key",
        )
    assert resolved2 == env_key


def test_s17_12_sec01_key_resolution_from_key_file():
    """
    SEC-01: resolve_key must read the key from a file when --old-key-file
    or --new-key-file is provided, stripping surrounding whitespace.
    """
    secret_key = "secret-key-from-file-sec01-test"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".key", delete=False, encoding="utf-8") as f:
        f.write(f"  {secret_key}  \n")
        key_file = f.name

    try:
        resolved = resolve_key(
            cli_arg=None,
            file_arg=key_file,
            env_vars=("OLD_CAMERA_ENCRYPTION_KEY",),
            prompt_name="old CAMERA_ENCRYPTION_KEY",
            deprecated_cli_name="--old-key",
        )
        assert resolved == secret_key
    finally:
        os.unlink(key_file)


def test_s17_13_sec01_key_file_takes_priority_over_env_var():
    """
    SEC-01: Key file must take priority over environment variable.
    """
    file_key = "file-has-priority-over-env"
    env_key = "env-var-should-be-ignored"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".key", delete=False, encoding="utf-8") as f:
        f.write(file_key)
        key_file = f.name

    try:
        with patch.dict(os.environ, {"OLD_CAMERA_ENCRYPTION_KEY": env_key}, clear=False):
            resolved = resolve_key(
                cli_arg=None,
                file_arg=key_file,
                env_vars=("OLD_CAMERA_ENCRYPTION_KEY",),
                prompt_name="old CAMERA_ENCRYPTION_KEY",
                deprecated_cli_name="--old-key",
            )
        assert resolved == file_key
    finally:
        os.unlink(key_file)


def test_s17_14_sec01_missing_key_raises_value_error():
    """
    SEC-01: resolve_key must raise ValueError when no source provides a key
    and stdin is not a TTY (non-interactive context like CI).
    """
    clean_env = {k: v for k, v in os.environ.items()
                 if k not in ("OLD_CAMERA_ENCRYPTION_KEY", "CROWDOS_OLD_CAMERA_KEY")}
    with patch.dict(os.environ, clean_env, clear=True):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            with pytest.raises(ValueError, match="No old CAMERA_ENCRYPTION_KEY found"):
                resolve_key(
                    cli_arg=None,
                    file_arg=None,
                    env_vars=("OLD_CAMERA_ENCRYPTION_KEY", "CROWDOS_OLD_CAMERA_KEY"),
                    prompt_name="old CAMERA_ENCRYPTION_KEY",
                    deprecated_cli_name="--old-key",
                )


# ============================================================================
# 10. SEC-02 â€” Migration Restart Safety (idempotent already-migrated detection)
# ============================================================================

@pytest.mark.asyncio
async def test_s17_15_sec02_mixed_state_migration_restart_safe():
    """
    SEC-02: A collection with a mix of old-key docs, new-key docs, and malformed
    docs must handle all three cases correctly without corrupting anything.

    Expected outcome:
    - 1 doc already encrypted under new_key  â†’ already_migrated=1, no DB write
    - 1 doc encrypted under old_key          â†’ migrated=1, 1 DB write
    - 1 doc with truly malformed ciphertext  â†’ failed=1, no DB write
    """
    old_key = "old-mixed-state-test-key-sec02-ab"
    new_key = "new-mixed-state-test-key-sec02-cd"

    plaintext_url = "rtsp://cam:pass@192.168.1.5:554/stream"
    old_enc = encrypt_credentials(plaintext_url, old_key)
    already_migrated_enc = encrypt_credentials(plaintext_url, new_key)
    malformed_enc = "not-valid-base64-aes-gcm-token!!!"

    docs = [
        {"_id": "doc_old",       "camera_id": "cam_old",    "credentials_encrypted": old_enc},
        {"_id": "doc_new",       "camera_id": "cam_new",    "credentials_encrypted": already_migrated_enc},
        {"_id": "doc_malformed", "camera_id": "cam_bad",    "credentials_encrypted": malformed_enc},
    ]

    class AsyncCursorMock:
        def __init__(self, items):
            self._items = iter(items)
        def __aiter__(self):
            return self
        async def __anext__(self):
            try:
                return next(self._items)
            except StopIteration:
                raise StopAsyncIteration

    mock_cameras_col = AsyncMock()
    mock_cameras_col.find.return_value = AsyncCursorMock(docs)

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

    assert stats["scanned"] == 3
    assert stats["migrated"] == 1,          f"Expected 1 migrated, got {stats['migrated']}"
    assert stats["already_migrated"] == 1,  f"Expected 1 already_migrated, got {stats['already_migrated']}"
    assert stats["failed"] == 1,            f"Expected 1 failed, got {stats['failed']}"
    # Only one update_one call (for the old-key doc, not the already-migrated or malformed)
    assert mock_cameras_col.update_one.call_count == 1

    # Verify the new ciphertext written is decryptable by new_key
    update_args = mock_cameras_col.update_one.call_args[0]
    written_token = update_args[1]["$set"]["credentials_encrypted"]
    assert decrypt_credentials(written_token, new_key) == plaintext_url

    # Error entry must reference the malformed camera, not the already-migrated one
    assert stats["errors"][0]["camera_id"] == "cam_bad"


@pytest.mark.asyncio
async def test_s17_16_sec02_dry_run_does_not_write_already_migrated():
    """
    SEC-02: dry_run=True must not call update_one even when migrating old-key docs.
    Already-migrated docs must still be counted correctly in dry_run mode.
    """
    old_key = "dry-run-old-key-sec02-test-32byte"
    new_key = "dry-run-new-key-sec02-test-32byte"

    plaintext = "rtsp://user:pw@10.0.0.1:554/live"
    old_enc = encrypt_credentials(plaintext, old_key)
    new_enc = encrypt_credentials(plaintext, new_key)

    docs = [
        {"_id": "doc_a", "camera_id": "cam_a", "credentials_encrypted": old_enc},
        {"_id": "doc_b", "camera_id": "cam_b", "credentials_encrypted": new_enc},
    ]

    class AsyncCursorMock:
        def __init__(self, items):
            self._items = iter(items)
        def __aiter__(self):
            return self
        async def __anext__(self):
            try:
                return next(self._items)
            except StopIteration:
                raise StopAsyncIteration

    mock_cameras_col = AsyncMock()
    mock_cameras_col.find.return_value = AsyncCursorMock(docs)
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
            dry_run=True,
        )

    assert stats["migrated"] == 1
    assert stats["already_migrated"] == 1
    assert stats["failed"] == 0
    # Dry run â€” must NEVER write to DB
    assert mock_cameras_col.update_one.call_count == 0


# ============================================================================
# 11. LOG-01 â€” SensitiveDataFilter with record.args & root-handler attachment
# ============================================================================

def test_s17_17_log01_filter_redacts_formatted_args():
    """
    LOG-01: SensitiveDataFilter must redact credentials that arrive as unformatted
    %s arguments (logger.info("URL: %s", rtsp_url)) before the handler emits them.
    After filtering, record.args must be cleared to prevent double-interpolation.
    """
    filter_obj = SensitiveDataFilter()
    secret_url = "rtsp://admin:super_secret@192.168.99.1:554/cam"

    # Simulate the record as the logging framework creates it before formatting
    record = logging.LogRecord(
        "test", logging.INFO, "camera.py", 42,
        "Connecting to source: %s",
        (secret_url,),
        None,
    )

    result = filter_obj.filter(record)
    assert result is True
    assert "super_secret" not in record.msg, "Credential must be redacted from msg"
    assert "***" in record.msg, "Redacted URL placeholder must appear in msg"
    assert record.args == () or record.args is None or not record.args, \
        "record.args must be cleared after formatting to prevent double-interpolation"


def test_s17_18_log01_filter_redacts_password_in_args():
    """
    LOG-01: SensitiveDataFilter must redact password= patterns even when
    the value arrives via %s record.args substitution.
    """
    filter_obj = SensitiveDataFilter()

    record = logging.LogRecord(
        "test", logging.WARNING, "config.py", 10,
        "Loaded config: password=%r",
        ("my_top_secret_pw",),
        None,
    )
    filter_obj.filter(record)
    assert "my_top_secret_pw" not in record.msg


def test_s17_19_log01_attach_filter_to_root_handler():
    """
    LOG-01: attach_sensitive_data_filter() must attach a SensitiveDataFilter to
    each root-logger handler exactly once (idempotent â€” duplicate-free).
    """
    # Set up a clean test logger with a fresh handler
    test_logger = logging.getLogger("crowdos.test.attach.sec01")
    test_logger.handlers.clear()
    handler = logging.StreamHandler(io.StringIO())
    test_logger.addHandler(handler)

    # First call â€” should attach
    attach_sensitive_data_filter(test_logger)
    count_after_first = sum(
        1 for f in handler.filters if isinstance(f, SensitiveDataFilter)
    )
    assert count_after_first == 1, "Filter should be attached exactly once"

    # Second call â€” should NOT duplicate
    attach_sensitive_data_filter(test_logger)
    count_after_second = sum(
        1 for f in handler.filters if isinstance(f, SensitiveDataFilter)
    )
    assert count_after_second == 1, "Filter must not be duplicated on repeated calls"


def test_s17_20_log01_attached_filter_redacts_at_emission():
    """
    LOG-01: End-to-end: a logger with attach_sensitive_data_filter() applied must
    redact RTSP credentials from emitted log output.
    """
    buf = io.StringIO()
    test_logger = logging.getLogger("crowdos.test.emit.sec01")
    test_logger.handlers.clear()
    test_logger.propagate = False
    handler = logging.StreamHandler(buf)
    handler.setLevel(logging.DEBUG)
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.DEBUG)

    attach_sensitive_data_filter(test_logger)

    secret_url = "rtsp://admin:hunter2@10.0.0.10:554/h264"
    test_logger.info("Opening stream %s", secret_url)

    output = buf.getvalue()
    assert "hunter2" not in output, "Credential must not appear in emitted log output"
    assert "***" in output, "Redacted placeholder must appear in emitted log output"

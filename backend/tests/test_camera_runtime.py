"""
Sprint 16 — Production Camera Runtime & Live AI Pipeline Tests.

Validates:
1. Camera source credential security & isolation (Critical Guard 1)
2. Deterministic event idempotency from source frame metadata (Critical Guard 2)
3. Camera lifecycle (start, stop, reconnect, stale detection, non-auto-start)
4. Monotonic time-based processing FPS sampling & bounded queues
5. Authoritative active session resolution & strict non-fabrication
6. Multi-camera and multi-venue isolation
7. Degraded mode & fault tolerance
8. Sprint 15 RBAC authorization
9. Privacy guarantees (zero biometrics, zero raw frames)
"""
import asyncio
import time
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from mongomock_motor import AsyncMongoMockClient

from app.core.settings import settings
from app.core.camera_security import (
    sanitize_source_url,
    sanitize_error_message,
    encrypt_credentials,
    decrypt_credentials,
    derive_deterministic_event_id,
)
from app.models.camera import CameraDBModel, CameraStatus
from app.models.user import UserDBModel, UserRole
from app.repositories.camera_repository import CameraRepository
from app.repositories.event_repository import EventRepository
from app.services.camera_runtime_service import (
    CameraRuntimeService,
    CameraRuntimeRecord,
    camera_runtime,
)
from app.services.event_service import EventService
from app.services.ai_engine_adapter import venue_registry
from app.schemas.cameras import CameraRegisterRequest
from app.realtime.schemas import (
    WebSocketEnvelope,
    WebSocketEventType,
    CameraHealthPayload,
)
from app.realtime.broadcaster import Broadcaster


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    client = AsyncMongoMockClient()
    return client["test_camera_db"]


@pytest.fixture
def camera_repo(mock_db):
    return CameraRepository(mock_db["cameras"])


@pytest.fixture
def event_repo(mock_db):
    return EventRepository(mock_db["events"])


@pytest.fixture
def runtime_service(camera_repo, event_repo):
    svc = CameraRuntimeService(
        camera_repo=camera_repo,
        event_service=EventService(registry=venue_registry, event_repo=event_repo),
        broadcaster_service=MagicMock(spec=Broadcaster),
    )
    svc._broadcaster.broadcast_camera_health_update = AsyncMock()
    return svc


class DummyFrame:
    def __init__(self, frame_number=1, timestamp=None):
        self.frame_number = frame_number
        self.timestamp = timestamp or time.time()
        self.frame = MagicMock()


# ---------------------------------------------------------------------------
# 1. Source Credential Security & Isolation (Critical Guard 1)
# ---------------------------------------------------------------------------

def test_s16_01_source_sanitizer_removes_credentials():
    url = "rtsp://admin:SecretPass123!@192.168.1.50:554/live"
    sanitized = sanitize_source_url(url)
    assert "SecretPass123!" not in sanitized
    assert "admin" not in sanitized
    assert "192.168.1.50:554/live" in sanitized
    assert sanitized == "rtsp://***:***@192.168.1.50:554/live"


def test_s16_02_source_sanitizer_handles_safe_sources():
    assert sanitize_source_url("0") == "0"
    assert sanitize_source_url("/dev/video0") == "/dev/video0"
    assert sanitize_source_url("rtsp://192.168.1.100:554/stream") == "rtsp://192.168.1.100:554/stream"
    assert sanitize_source_url("") == ""
    assert sanitize_source_url(None) == ""


def test_s16_03_credential_encryption_roundtrip():
    secret = "rtsp://alice:SuperSecret_2026!@cam.secure.net/live"
    encrypted = encrypt_credentials(secret, settings.SECRET_KEY)
    assert secret not in encrypted

    decrypted = decrypt_credentials(encrypted, settings.SECRET_KEY)
    assert decrypted == secret

    # Tampering check
    tampered = encrypted[:-4] + "AAAA"
    with pytest.raises(Exception):
        decrypt_credentials(tampered, settings.SECRET_KEY)


def test_s16_04_error_message_sanitizer():
    err = "Connection failed for rtsp://operator:p@ss123@10.0.0.1:554/ch0: connection timeout"
    cleaned = sanitize_error_message(err)
    assert "p@ss123" not in cleaned
    assert "operator" not in cleaned
    assert "rtsp://***:***@10.0.0.1:554/ch0" in cleaned


@pytest.mark.asyncio
async def test_s16_05_camera_registration_isolates_and_encrypts_credentials(runtime_service, camera_repo):
    venue_id = "venue_sec_1"
    raw_source = "rtsp://admin:ClassifiedPassword@192.168.1.200:554/stream"

    req = CameraRegisterRequest(
        camera_name="Main Gate Cam",
        camera_type="rtsp",
        camera_source=raw_source,
        gate_id="gate_north",
    )
    res = await runtime_service.register_camera(venue_id, req)

    # API Response must NOT leak plaintext credentials
    assert "ClassifiedPassword" not in res.camera_source_masked
    assert res.camera_source_masked == "rtsp://***:***@192.168.1.200:554/stream"

    # In MongoDB: plaintext source must NOT have credentials; encrypted payload exists
    doc = await camera_repo.get_by_camera_id(res.camera_id)
    assert doc is not None
    assert "ClassifiedPassword" not in doc.camera_source
    assert doc.credentials_encrypted is not None
    assert "ClassifiedPassword" not in doc.credentials_encrypted

    # Internal runtime in-memory decryption matches original
    decrypted = runtime_service._get_decrypted_source(doc)
    assert decrypted == raw_source


# ---------------------------------------------------------------------------
# 2. Deterministic Event Idempotency (Critical Guard 2)
# ---------------------------------------------------------------------------

def test_s16_06_deterministic_event_id_stability():
    camera_id = "cam_east_01"
    gate_id = "gate_east"
    frame_num = 142
    ts = 1726000000.12345

    id_1 = derive_deterministic_event_id(camera_id, gate_id, frame_num, ts)
    id_2 = derive_deterministic_event_id(camera_id, gate_id, frame_num, ts)
    assert id_1 == id_2  # Strictly equal

    # Different frame number -> different ID
    id_3 = derive_deterministic_event_id(camera_id, gate_id, frame_num + 1, ts)
    assert id_1 != id_3


@pytest.mark.asyncio
async def test_s16_07_duplicate_frame_processing_is_idempotent(runtime_service, event_repo):
    venue_id = "venue_idempotent_test"
    camera_id = "cam_idem_1"

    # Setup active session in intelligence engine
    engines = venue_registry.get_or_create(venue_id)
    session = engines.intelligence.session_manager.create_session(venue_id=venue_id)
    engines.intelligence.session_manager.start_session(session.session_id)

    # Setup camera record with override pipeline producing an entry event
    rec = CameraRuntimeRecord(
        camera_id=camera_id,
        venue_id=venue_id,
        camera_name="Idempotency Cam",
        camera_type="rtsp",
        raw_source="0",
        gate_id="gate_1",
        status=CameraStatus.ONLINE,
        ai_pipeline_override=lambda c, f: {"event_type": "ENTRY", "visitor_id": "vis_101"},
    )
    runtime_service._records[camera_id] = rec

    # Process identical frame twice (same frame_number and timestamp)
    frame = DummyFrame(frame_number=42, timestamp=1726000000.5)
    await runtime_service._frame_callback(camera_id, frame)

    # Reset monotonic limiter to allow second call with identical source frame
    rec.last_processed_monotonic = 0.0
    await runtime_service._frame_callback(camera_id, frame)

    # Verify only ONE event document was persisted in MongoDB
    events = await event_repo.list_events_by_venue(venue_id)
    assert len(events) == 1


# ---------------------------------------------------------------------------
# 3. Camera Lifecycle & Startup Reconciliation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_s16_08_new_camera_status_is_registered(runtime_service):
    res = await runtime_service.register_camera(
        "venue_test_life",
        CameraRegisterRequest(camera_name="Cam 1", camera_type="usb", camera_source="0"),
    )
    assert res.status == "REGISTERED"


@pytest.mark.asyncio
async def test_s16_09_startup_reconciliation_marks_stale_cameras_offline(camera_repo, runtime_service):
    # Insert cameras with stale status
    now = datetime.now(timezone.utc)
    cam1 = CameraDBModel(
        camera_id="cam_stale_1",
        venue_id="venue_1",
        camera_name="Cam 1",
        camera_type="rtsp",
        camera_source="rtsp://localhost/1",
        status=CameraStatus.ONLINE,
        created_at=now,
    )
    cam2 = CameraDBModel(
        camera_id="cam_stale_2",
        venue_id="venue_1",
        camera_name="Cam 2",
        camera_type="rtsp",
        camera_source="rtsp://localhost/2",
        status=CameraStatus.RECONNECTING,
        created_at=now,
    )
    await camera_repo.save_camera(cam1)
    await camera_repo.save_camera(cam2)

    # Simulate application restart
    await runtime_service.start_runtime()

    updated1 = await camera_repo.get_by_camera_id("cam_stale_1")
    updated2 = await camera_repo.get_by_camera_id("cam_stale_2")
    assert updated1.status == CameraStatus.OFFLINE
    assert updated2.status == CameraStatus.OFFLINE

    await runtime_service.stop_runtime()


@pytest.mark.asyncio
async def test_s16_10_camera_start_and_stop_lifecycle(runtime_service):
    """Validates start/stop contract independent of physical hardware/file system.

    The underlying ai-engine camera manager's start_camera() is patched so
    the test does not depend on a real RTSP server, video file, or USB device.
    This keeps the test deterministic in CI without touching any Sprint 15 logic.
    """
    venue_id = "venue_start_stop"
    res = await runtime_service.register_camera(
        venue_id,
        CameraRegisterRequest(camera_name="Test Stream", camera_type="file", camera_source="dummy.mp4"),
    )
    camera_id = res.camera_id

    # Patch start_camera on the venue's manager so the test is hardware-independent
    manager = runtime_service._get_or_create_manager(venue_id)
    with patch.object(manager, "start_camera", new=AsyncMock(return_value=True)):
        action_start = await runtime_service.start_camera(venue_id, camera_id)

    assert action_start.success is True
    assert action_start.status == "ONLINE"

    # Stop camera — no patch needed; stop always succeeds in the service layer
    action_stop = await runtime_service.stop_camera(venue_id, camera_id)
    assert action_stop.success is True
    assert action_stop.status == "OFFLINE"


@pytest.mark.asyncio
async def test_s16_11_stale_camera_detected_and_degraded(runtime_service):
    venue_id = "venue_stale_eval"
    res = await runtime_service.register_camera(
        venue_id,
        CameraRegisterRequest(camera_name="Stale Cam", camera_type="usb", camera_source="0"),
    )
    camera_id = res.camera_id
    rec = runtime_service._records[camera_id]
    rec.status = CameraStatus.ONLINE
    # Frame received 25 seconds ago (> 10s threshold)
    rec.last_frame_at = datetime.fromtimestamp(time.time() - 25.0, timezone.utc)

    health = await runtime_service.get_camera_health(venue_id, camera_id)
    assert health.status == "DEGRADED"


# ---------------------------------------------------------------------------
# 4. Processing FPS Rate Limiting & Queue Bounds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_s16_12_time_based_processing_rate_limiter(runtime_service):
    venue_id = "venue_fps_limiter"
    camera_id = "cam_high_fps"

    engines = venue_registry.get_or_create(venue_id)
    session = engines.intelligence.session_manager.create_session(venue_id=venue_id)
    engines.intelligence.session_manager.start_session(session.session_id)

    processed_count = 0

    def mock_pipeline(c, f):
        nonlocal processed_count
        processed_count += 1
        return {"event_type": "ENTRY"}

    rec = CameraRuntimeRecord(
        camera_id=camera_id,
        venue_id=venue_id,
        camera_name="Fast Cam",
        camera_type="usb",
        raw_source="0",
        status=CameraStatus.ONLINE,
        ai_pipeline_override=mock_pipeline,
    )
    runtime_service._records[camera_id] = rec

    # Simulate 30 frames arriving within 0.05 seconds (600 FPS burst)
    for i in range(30):
        frame = DummyFrame(frame_number=i + 1, timestamp=time.time())
        await runtime_service._frame_callback(camera_id, frame)

    # Since interval is 1/5 = 0.200s, only the first frame should process
    assert processed_count == 1


# ---------------------------------------------------------------------------
# 5. Authoritative Session Resolution & Non-Fabrication Invariants
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_s16_13_no_active_session_discards_frame(runtime_service, event_repo):
    venue_id = "venue_no_session"
    camera_id = "cam_no_sess"

    # Make sure venue exists but has NO active session
    engines = venue_registry.get_or_create(venue_id)
    engines.intelligence.session_manager.clear()

    rec = CameraRuntimeRecord(
        camera_id=camera_id,
        venue_id=venue_id,
        camera_name="No Sess Cam",
        camera_type="usb",
        raw_source="0",
        status=CameraStatus.ONLINE,
        ai_pipeline_override=lambda c, f: {"event_type": "ENTRY"},
    )
    runtime_service._records[camera_id] = rec

    frame = DummyFrame(frame_number=1)
    await runtime_service._frame_callback(camera_id, frame)

    events = await event_repo.list_events_by_venue(venue_id)
    assert len(events) == 0  # Zero events ingested


@pytest.mark.asyncio
async def test_s16_14_pipeline_stub_does_not_fabricate_events(runtime_service, event_repo):
    venue_id = "venue_non_fab"
    camera_id = "cam_stub"

    engines = venue_registry.get_or_create(venue_id)
    session = engines.intelligence.session_manager.create_session(venue_id=venue_id)
    engines.intelligence.session_manager.start_session(session.session_id)

    # Empty result / stub result from frozen pipeline
    rec = CameraRuntimeRecord(
        camera_id=camera_id,
        venue_id=venue_id,
        camera_name="Stub Cam",
        camera_type="usb",
        raw_source="0",
        status=CameraStatus.ONLINE,
        ai_pipeline_override=lambda c, f: {"pipeline": "camera", "frame_id": 0},
    )
    runtime_service._records[camera_id] = rec

    frame = DummyFrame(frame_number=1)
    await runtime_service._frame_callback(camera_id, frame)

    # Strict invariant: NO event fabricated
    events = await event_repo.list_events_by_venue(venue_id)
    assert len(events) == 0


# ---------------------------------------------------------------------------
# 6. Multi-Camera & Multi-Venue Isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_s16_15_sibling_cameras_operate_independently(runtime_service):
    venue_id = "venue_multi_cam"
    c1 = await runtime_service.register_camera(venue_id, CameraRegisterRequest(camera_name="Cam 1", camera_type="usb", camera_source="0"))
    c2 = await runtime_service.register_camera(venue_id, CameraRegisterRequest(camera_name="Cam 2", camera_type="usb", camera_source="1"))

    # Starting Cam 1 does not affect Cam 2 status (hardware-independent via patched start_camera)
    manager = runtime_service._get_or_create_manager(venue_id)
    with patch.object(manager, "start_camera", new=AsyncMock(return_value=True)):
        await runtime_service.start_camera(venue_id, c1.camera_id)
    h1 = await runtime_service.get_camera_health(venue_id, c1.camera_id)
    h2 = await runtime_service.get_camera_health(venue_id, c2.camera_id)

    assert h1.status == "ONLINE"
    assert h2.status == "REGISTERED"


@pytest.mark.asyncio
async def test_s16_16_cross_venue_camera_access_denied(runtime_service):
    v1 = "venue_alpha"
    v2 = "venue_beta"

    cam = await runtime_service.register_camera(v1, CameraRegisterRequest(camera_name="Alpha Cam", camera_type="usb", camera_source="0"))

    # Attempting to access camera under venue_beta raises NotFoundException
    with pytest.raises(Exception) as exc_info:
        await runtime_service.get_camera(v2, cam.camera_id)
    assert "not found" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 7. Privacy Compliance
# ---------------------------------------------------------------------------

def test_s16_17_camera_db_model_rejects_biometric_fields():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError) as exc:
        CameraDBModel(
            camera_id="cam_priv_1",
            venue_id="venue_1",
            camera_name="Priv Cam",
            camera_type="usb",
            camera_source="0",
            status=CameraStatus.REGISTERED,
            created_at=now,
            face_embedding=[0.12, 0.44],  # Prohibited!
        )
    assert "PRIVACY VIOLATION" in str(exc.value)


def test_s16_18_camera_health_payload_rejects_biometrics():
    with pytest.raises(ValueError) as exc:
        WebSocketEnvelope(
            type=WebSocketEventType.CAMERA_HEALTH_UPDATE,
            venue_id="venue_1",
            data={
                "camera_id": "cam_1",
                "venue_id": "venue_1",
                "status": "ONLINE",
                "raw_frame": "binary_data",  # Prohibited!
            },
        )
    assert "PRIVACY VIOLATION" in str(exc.value)


# ---------------------------------------------------------------------------
# 8. RBAC & REST API Integration Tests
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient
from app.main import app
from app.dependencies.auth import get_current_user, require_venue_access


@pytest.fixture
def test_client():
    return TestClient(app)


def test_s16_19_analyst_cannot_start_camera(test_client):
    analyst_user = UserDBModel(
        user_id="user_analyst_1",
        email="analyst@crowdos.test",
        password_hash="",
        display_name="Analyst",
        role=UserRole.ANALYST,
        venue_ids=["venue_auth_1"],
        is_active=True,
    )

    app.dependency_overrides[get_current_user] = lambda: analyst_user
    try:
        res = test_client.post("/api/v1/venues/venue_auth_1/cameras/cam_1/start")
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_s16_20_operator_cannot_register_or_delete_camera(test_client):
    operator_user = UserDBModel(
        user_id="user_operator_1",
        email="operator@crowdos.test",
        password_hash="",
        display_name="Operator",
        role=UserRole.OPERATOR,
        venue_ids=["venue_auth_1"],
        is_active=True,
    )

    app.dependency_overrides[get_current_user] = lambda: operator_user
    try:
        # Operator cannot register
        res1 = test_client.post(
            "/api/v1/venues/venue_auth_1/cameras",
            json={"camera_name": "Test", "camera_type": "usb", "camera_source": "0"},
        )
        assert res1.status_code == 403

        # Operator cannot delete
        res2 = test_client.delete("/api/v1/venues/venue_auth_1/cameras/cam_1")
        assert res2.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_s16_21_venue_admin_can_register_and_list_cameras(test_client):
    admin_user = UserDBModel(
        user_id="user_admin_1",
        email="admin@crowdos.test",
        password_hash="",
        display_name="Venue Admin",
        role=UserRole.VENUE_ADMIN,
        venue_ids=["venue_auth_1"],
        is_active=True,
    )

    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        res = test_client.post(
            "/api/v1/venues/venue_auth_1/cameras",
            json={
                "camera_name": "Front Gate",
                "camera_type": "rtsp",
                "camera_source": "rtsp://user:pass@192.168.1.10:554/stream",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["camera_name"] == "Front Gate"
        assert "pass" not in data["camera_source_masked"]
        assert data["status"] == "REGISTERED"

        # List cameras
        list_res = test_client.get("/api/v1/venues/venue_auth_1/cameras")
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["total"] >= 1
    finally:
        app.dependency_overrides.clear()


def test_s16_22_cross_venue_access_forbidden(test_client):
    venue_user = UserDBModel(
        user_id="user_v1",
        email="user@v1.test",
        password_hash="",
        display_name="Venue 1 Admin",
        role=UserRole.VENUE_ADMIN,
        venue_ids=["venue_permitted"],
        is_active=True,
    )

    app.dependency_overrides[get_current_user] = lambda: venue_user
    try:
        # Attempt to access venue_forbidden
        res = test_client.get("/api/v1/venues/venue_forbidden/cameras")
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 9. Degraded Mode & Fault Tolerance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_s16_23_degraded_mode_db_unavailable_streaming_continues(runtime_service):
    # Simulate DB unavailable
    runtime_service._camera_repo = None
    venue_id = "venue_degraded"

    res = await runtime_service.register_camera(
        venue_id,
        CameraRegisterRequest(camera_name="Degraded Cam", camera_type="usb", camera_source="0"),
    )
    assert res.status == "REGISTERED"

    # Start camera works in memory (hardware-independent via patched start_camera)
    manager = runtime_service._get_or_create_manager(venue_id)
    with patch.object(manager, "start_camera", new=AsyncMock(return_value=True)):
        start_res = await runtime_service.start_camera(venue_id, res.camera_id)
    assert start_res.success is True
    assert start_res.status == "ONLINE"

    # Health check works in memory
    health = await runtime_service.get_camera_health(venue_id, res.camera_id)
    assert health.status == "ONLINE"


@pytest.mark.asyncio
async def test_s16_24_ai_exception_does_not_crash_pipeline(runtime_service):
    venue_id = "venue_ai_err"
    camera_id = "cam_err"

    engines = venue_registry.get_or_create(venue_id)
    session = engines.intelligence.session_manager.create_session(venue_id=venue_id)
    engines.intelligence.session_manager.start_session(session.session_id)

    def faulty_pipeline(c, f):
        raise RuntimeError("GPU CUDA out of memory in rtsp://user:pass@192.168.1.1:554")

    rec = CameraRuntimeRecord(
        camera_id=camera_id,
        venue_id=venue_id,
        camera_name="Faulty Cam",
        camera_type="usb",
        raw_source="0",
        status=CameraStatus.ONLINE,
        ai_pipeline_override=faulty_pipeline,
    )
    runtime_service._records[camera_id] = rec

    frame = DummyFrame(frame_number=1)
    # Must NOT raise unhandled exception
    await runtime_service._frame_callback(camera_id, frame)

    assert rec.last_error_at is not None
    assert "pass" not in rec.last_error_message
    assert "GPU CUDA out of memory" in rec.last_error_message


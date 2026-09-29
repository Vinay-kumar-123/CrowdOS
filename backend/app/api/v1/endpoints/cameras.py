"""
Camera Endpoints — Sprint 16.

REST API for camera registration, stream control, and live health inspection.
Strictly venue-scoped and protected by Sprint 15 RBAC authorization.

Role Authorization Matrix:
- ANALYST: Read-only (list, get, health)
- OPERATOR: Read-only + Stream control (start, stop)
- VENUE_ADMIN: Full venue access (register, delete, start, stop)
- SUPER_ADMIN: Full platform access
"""
from fastapi import APIRouter, Depends, status
from typing import Any
from app.models.user import UserRole
from app.dependencies.auth import require_venue_access, require_role
from app.dependencies.database import (
    get_camera_repository,
    get_event_repository,
    get_alert_repository,
    get_visitor_event_repository,
    get_visitor_repository,
    get_visit_repository,
)
from app.repositories.camera_repository import CameraRepository
from app.services.camera_runtime_service import CameraRuntimeService, camera_runtime
from app.services.event_service import EventService
from app.services.visitor_history_service import VisitorHistoryService
from app.services.ai_engine_adapter import venue_registry
from app.realtime.broadcaster import broadcaster
from app.schemas.cameras import (
    CameraRegisterRequest,
    CameraResponse,
    CameraHealthResponse,
    CameraListResponse,
    CameraActionResponse,
)

router = APIRouter(
    prefix="/v1/venues/{venue_id}/cameras",
    tags=["Cameras"],
    dependencies=[Depends(require_venue_access)],
)

# RBAC permission groups
_require_analyst = Depends(require_role(UserRole.ANALYST, UserRole.OPERATOR, UserRole.VENUE_ADMIN, UserRole.SUPER_ADMIN))
_require_operator = Depends(require_role(UserRole.OPERATOR, UserRole.VENUE_ADMIN, UserRole.SUPER_ADMIN))
_require_admin = Depends(require_role(UserRole.VENUE_ADMIN, UserRole.SUPER_ADMIN))


def _get_camera_service(
    camera_repo: CameraRepository = Depends(get_camera_repository),
    event_repo=Depends(get_event_repository),
    alert_repo=Depends(get_alert_repository),
    v_repo=Depends(get_visitor_repository),
    ve_repo=Depends(get_visitor_event_repository),
    vi_repo=Depends(get_visit_repository),
) -> CameraRuntimeService:
    """Dependency provider injecting database repositories into CameraRuntimeService."""
    visitor_history_svc = VisitorHistoryService(
        visitor_repo=v_repo,
        event_repo=ve_repo,
        visit_repo=vi_repo,
    )
    event_svc = EventService(
        registry=venue_registry,
        event_repo=event_repo,
        alert_repo=alert_repo,
        visitor_history_svc=visitor_history_svc,
    )
    camera_runtime._camera_repo = camera_repo
    camera_runtime._event_service = event_svc
    camera_runtime._broadcaster = broadcaster
    return camera_runtime


@router.post(
    "",
    response_model=CameraResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register camera",
    description="Registers a new camera for the venue in REGISTERED state. Credentials are encrypted and never returned.",
)
async def register_camera(
    venue_id: str,
    body: CameraRegisterRequest,
    svc: CameraRuntimeService = Depends(_get_camera_service),
    _role: Any = _require_admin,
):
    return await svc.register_camera(venue_id=venue_id, request=body)


@router.get(
    "",
    response_model=CameraListResponse,
    summary="List venue cameras",
    description="Returns all cameras registered to the venue with live telemetry overlay and masked credentials.",
)
async def list_cameras(
    venue_id: str,
    svc: CameraRuntimeService = Depends(_get_camera_service),
    _role: Any = _require_analyst,
):
    return await svc.list_cameras(venue_id=venue_id)


@router.get(
    "/{camera_id}",
    response_model=CameraResponse,
    summary="Get camera details",
    description="Returns details for a specific camera with masked credentials.",
)
async def get_camera(
    venue_id: str,
    camera_id: str,
    svc: CameraRuntimeService = Depends(_get_camera_service),
    _role: Any = _require_analyst,
):
    return await svc.get_camera(venue_id=venue_id, camera_id=camera_id)


@router.delete(
    "/{camera_id}",
    summary="Delete camera",
    description="Stops stream if running and removes camera registration.",
)
async def delete_camera(
    venue_id: str,
    camera_id: str,
    svc: CameraRuntimeService = Depends(_get_camera_service),
    _role: Any = _require_admin,
):
    deleted = await svc.delete_camera(venue_id=venue_id, camera_id=camera_id)
    return {"status": "success", "message": f"Camera '{camera_id}' deleted successfully.", "deleted": deleted}


@router.post(
    "/{camera_id}/start",
    response_model=CameraActionResponse,
    summary="Start camera capture stream",
    description="Explicitly launches physical camera capture stream. Operator or admin privileges required.",
)
async def start_camera(
    venue_id: str,
    camera_id: str,
    svc: CameraRuntimeService = Depends(_get_camera_service),
    _role: Any = _require_operator,
):
    return await svc.start_camera(venue_id=venue_id, camera_id=camera_id)


@router.post(
    "/{camera_id}/stop",
    response_model=CameraActionResponse,
    summary="Stop camera capture stream",
    description="Stops physical camera capture stream. Operator or admin privileges required.",
)
async def stop_camera(
    venue_id: str,
    camera_id: str,
    svc: CameraRuntimeService = Depends(_get_camera_service),
    _role: Any = _require_operator,
):
    return await svc.stop_camera(venue_id=venue_id, camera_id=camera_id)


@router.get(
    "/{camera_id}/health",
    response_model=CameraHealthResponse,
    summary="Get camera health and telemetry",
    description="Returns real-time health score, measured FPS, latency, and stale stream detection.",
)
async def get_camera_health(
    venue_id: str,
    camera_id: str,
    svc: CameraRuntimeService = Depends(_get_camera_service),
    _role: Any = _require_analyst,
):
    return await svc.get_camera_health(venue_id=venue_id, camera_id=camera_id)

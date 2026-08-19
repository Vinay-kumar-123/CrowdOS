"""
Venue Endpoints — Sprint 9.

REST API for venue registry management.

Routes:
    GET  /v1/venues                   → list registered venues
    GET  /v1/venues/{venue_id}        → venue info + engine status
    POST /v1/venues/{venue_id}/reset  → reset venue engine state (testing only)
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from app.services.ai_engine_adapter import venue_registry
from app.schemas.events import VenueInfoResponse

router = APIRouter(prefix="/v1/venues", tags=["Venues"])


@router.get(
    "",
    response_model=List[str],
    summary="List registered venues",
    description="Returns a list of all venue IDs currently initialized in the in-memory VenueEngineRegistry.",
)
async def list_venues():
    return venue_registry.list_venue_ids()


@router.get(
    "/{venue_id}",
    response_model=VenueInfoResponse,
    summary="Get venue information",
    description="Returns metadata, configured capacity, active session ID, and engine availability for the specified venue.",
)
async def get_venue_info(venue_id: str):
    engines = venue_registry.get(venue_id)
    if engines is None:
        raise HTTPException(status_code=404, detail=f"Venue '{venue_id}' not found.")

    active_session = engines.intelligence.session_manager.get_active_session()

    return VenueInfoResponse(
        venue_id=venue_id,
        venue_capacity=engines.venue_capacity,
        ai_engine_available=venue_registry.is_ai_engine_available,
        active_session_id=active_session.session_id if active_session else None,
        registered_venues=len(venue_registry.list_venue_ids()),
    )


@router.post(
    "/{venue_id}/reset",
    response_model=Dict[str, Any],
    summary="Reset venue engine state",
    description="Clears all in-memory Movement, Intelligence, and Prediction engine state for the specified venue (testing utility).",
)
async def reset_venue(venue_id: str):
    success = venue_registry.reset_venue(venue_id)
    return {
        "venue_id": venue_id,
        "reset": success,
        "message": f"Venue '{venue_id}' engine state cleared." if success else f"Venue '{venue_id}' not found.",
    }

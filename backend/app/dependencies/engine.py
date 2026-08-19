"""
FastAPI dependency injection for AI Engine Registry — Sprint 9.

Provides get_venue_engines() as a FastAPI Depends() callable that
resolves the VenueEngineRegistry and returns the correct VenueEngines.
"""
from fastapi import Depends, HTTPException, status
from app.services.ai_engine_adapter import venue_registry, VenueEngines


def get_registry():
    """Dependency: returns the global VenueEngineRegistry singleton."""
    return venue_registry


def get_venue_engines(venue_id: str, registry=Depends(get_registry)) -> VenueEngines:
    """
    FastAPI dependency: resolve VenueEngines for a given venue_id.
    Raises 404 if the venue has not been initialized (no session created yet).
    Use get_or_create_venue_engines() for endpoints that should auto-initialize.
    """
    engines = registry.get(venue_id)
    if engines is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Venue '{venue_id}' not found. Create a session first.",
        )
    return engines


def get_or_create_venue_engines(
    venue_id: str,
    venue_capacity: int = 1000,
    registry=Depends(get_registry),
) -> VenueEngines:
    """
    FastAPI dependency: get or create VenueEngines for a given venue_id.
    Used by session-creation and event-ingest endpoints.
    """
    return registry.get_or_create(venue_id=venue_id, venue_capacity=venue_capacity)

"""
FastAPI Dependency Injection for MongoDB Repositories — Sprint 10.
"""
from app.database.mongodb.connection import db_connection
from app.repositories.venue_repository import VenueRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.event_repository import EventRepository
from app.repositories.alert_repository import AlertRepository
from app.repositories.prediction_repository import PredictionRepository
from app.repositories.visitor_repository import (
    VisitorRepository,
    VisitorEventRepository,
    VisitRepository,
)


def get_venue_repository() -> VenueRepository:
    """Dependency provider for VenueRepository."""
    collection = db_connection.get_collection("venues")
    return VenueRepository(collection)


def get_session_repository() -> SessionRepository:
    """Dependency provider for SessionRepository."""
    collection = db_connection.get_collection("sessions")
    return SessionRepository(collection)


def get_event_repository() -> EventRepository:
    """Dependency provider for EventRepository."""
    collection = db_connection.get_collection("events")
    return EventRepository(collection)


def get_alert_repository() -> AlertRepository:
    """Dependency provider for AlertRepository."""
    collection = db_connection.get_collection("alerts")
    return AlertRepository(collection)


def get_prediction_repository() -> PredictionRepository:
    """Dependency provider for PredictionRepository."""
    collection = db_connection.get_collection("predictions")
    return PredictionRepository(collection)


def get_visitor_repository() -> VisitorRepository:
    """Dependency provider for VisitorRepository."""
    collection = db_connection.get_collection("visitors")
    return VisitorRepository(collection)


def get_visitor_event_repository() -> VisitorEventRepository:
    """Dependency provider for VisitorEventRepository."""
    collection = db_connection.get_collection("visitor_events")
    return VisitorEventRepository(collection)


def get_visit_repository() -> VisitRepository:
    """Dependency provider for VisitRepository."""
    collection = db_connection.get_collection("visits")
    return VisitRepository(collection)


def get_redis_client():
    """Dependency provider for Upstash Redis client. Returns None in degraded mode."""
    from app.database.redis.connection import redis_connection
    return redis_connection.get_client()

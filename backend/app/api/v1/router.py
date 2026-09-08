"""
API v1 Router — Sprint 9.

Registers all Sprint 9 endpoint routers.
Includes: health, status, venues, sessions, events, intelligence, predictions, alerts, dashboard.
"""
from fastapi import APIRouter
from app.api.v1.endpoints import (
    health, status, sessions, intelligence, predictions, events, alerts, venues, dashboard, visitors, visitor_analytics, auth, users
)

api_router = APIRouter()

# Core system endpoints
api_router.include_router(health.router)
api_router.include_router(status.router)

# Sprint 15 — Operator Authentication & User Management Layer
api_router.include_router(auth.router)
api_router.include_router(users.router)

# Sprint 9 — AI Engine Integration Layer
api_router.include_router(venues.router)
api_router.include_router(sessions.router)
api_router.include_router(events.router)
api_router.include_router(intelligence.router)
api_router.include_router(predictions.router)
api_router.include_router(alerts.router)
api_router.include_router(dashboard.router)

# Sprint 13 — Visitor Event & History Persistence Layer
api_router.include_router(visitors.router)

# Sprint 14 — Visitor Analytics & History Intelligence Layer
api_router.include_router(visitor_analytics.router)

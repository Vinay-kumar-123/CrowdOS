"""
Visitor Analytics Schemas — Sprint 14.

Defines Pydantic response models for visitor and venue analytics:
- VisitorAnalyticsSummaryResponse: Consolidated visitor profile analytics
- VisitorDailyAnalyticsResponse / Item: Day-by-day visitor metrics
- VisitorFrequencyResponse: Visit frequency and return pattern
- VisitorGateAnalyticsResponse / Item: Gate usage counts, percentages, and top gates
- VisitorDurationAnalyticsResponse: Duration distribution for completed visits
- VisitorTimelineResponse / DayItem: Chronological timeline preserving multiple visits per day
- VenueVisitorAnalyticsResponse: Venue-wide aggregate visitor intelligence
- VenueDailyTrendsResponse / Item: Venue-wide daily trend trajectory
- VenueAnalyticsSummaryResponse: Consolidated venue analytics summary

Privacy guarantee:
Enforces recursive biometric ban on all models.
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, model_validator
from app.models.event import PROHIBITED_BIOMETRIC_FIELDS


def _assert_no_biometrics_recursive(data: Any, path: str = "") -> None:
    """Recursively enforce that no prohibited biometric field is present."""
    if isinstance(data, dict):
        for k, v in data.items():
            current_path = f"{path}.{k}" if path else str(k)
            if str(k).lower() in PROHIBITED_BIOMETRIC_FIELDS and v is not None:
                raise ValueError(
                    f"PRIVACY VIOLATION: Prohibited biometric field '{k}' found at '{current_path}'."
                )
            _assert_no_biometrics_recursive(v, current_path)
    elif isinstance(data, (list, tuple, set)):
        for idx, item in enumerate(data):
            _assert_no_biometrics_recursive(item, f"{path}[{idx}]")


class PrivacyValidatedModel(BaseModel):
    """Base model that validates no biometric field is ever injected."""

    @model_validator(mode="before")
    @classmethod
    def validate_privacy(cls, data: Any):
        if isinstance(data, dict):
            _assert_no_biometrics_recursive(data)
        return data


# ============================================================================
# Gate Analytics
# ============================================================================

class GateUsageItem(PrivacyValidatedModel):
    """Usage counts and percentage for a specific gate."""
    gate_id: str
    count: int = Field(default=0, ge=0)
    percentage: float = Field(default=0.0, ge=0.0, le=100.0)


class VisitorGateAnalyticsResponse(PrivacyValidatedModel):
    """Gate usage breakdown for entries and exits."""
    visitor_id: Optional[str] = None
    venue_id: str
    total_entries: int = Field(default=0, ge=0)
    total_exits: int = Field(default=0, ge=0)
    entry_gates: List[GateUsageItem] = Field(default_factory=list)
    exit_gates: List[GateUsageItem] = Field(default_factory=list)
    most_used_entry_gate: Optional[str] = None
    most_used_exit_gate: Optional[str] = None


# ============================================================================
# Visit Duration Analytics
# ============================================================================

class VisitorDurationAnalyticsResponse(PrivacyValidatedModel):
    """Duration statistics for completed visits only."""
    visitor_id: Optional[str] = None
    venue_id: str
    completed_visits_count: int = Field(default=0, ge=0)
    open_visits_excluded_count: int = Field(default=0, ge=0)
    total_duration_seconds: float = Field(default=0.0, ge=0.0)
    average_duration_seconds: Optional[float] = None
    minimum_duration_seconds: Optional[float] = None
    maximum_duration_seconds: Optional[float] = None
    median_duration_seconds: Optional[float] = None


# ============================================================================
# Visitor Frequency & Returning Classification
# ============================================================================

class VisitorFrequencyResponse(PrivacyValidatedModel):
    """Visit frequency and returning pattern metrics for a visitor."""
    visitor_id: str
    venue_id: str
    total_visits: int = Field(default=0, ge=0)
    completed_visits: int = Field(default=0, ge=0)
    open_visits: int = Field(default=0, ge=0)
    unique_active_days: int = Field(default=0, ge=0)
    days_since_first_visit: int = Field(default=0, ge=0)
    visits_per_day: float = Field(default=0.0, ge=0.0)
    average_visits_per_active_day: float = Field(default=0.0, ge=0.0)
    is_returning_visitor: bool = Field(
        default=False,
        description="True if visitor has total_visits > 1 (more than one valid visit record)",
    )


# ============================================================================
# Visitor Profile Summary Analytics
# ============================================================================

class VisitorAnalyticsSummaryResponse(PrivacyValidatedModel):
    """Comprehensive visitor profile analytics."""
    visitor_id: str
    venue_id: str
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    total_entries: int = Field(default=0, ge=0)
    total_exits: int = Field(default=0, ge=0)
    total_visits: int = Field(
        default=0,
        ge=0,
        description="Number of valid ENTRY events that created a Visit record, including currently OPEN visits",
    )
    completed_visits: int = Field(default=0, ge=0)
    open_visits: int = Field(default=0, ge=0)
    average_visit_duration_seconds: Optional[float] = None
    minimum_visit_duration_seconds: Optional[float] = None
    maximum_visit_duration_seconds: Optional[float] = None
    total_visit_duration_seconds: float = Field(default=0.0, ge=0.0)
    unique_visit_days: int = Field(default=0, ge=0)
    first_visit_at: Optional[str] = None
    last_visit_at: Optional[str] = None
    is_returning_visitor: bool = Field(default=False)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Daily Visitor Analytics
# ============================================================================

class VisitorDailyAnalyticsItem(PrivacyValidatedModel):
    """Daily movement and presence metrics for a visitor."""
    date: str = Field(..., description="UTC date string (YYYY-MM-DD)")
    total_entries: int = Field(default=0, ge=0)
    total_exits: int = Field(default=0, ge=0)
    total_visits_started: int = Field(default=0, ge=0)
    completed_visits: int = Field(default=0, ge=0)
    open_visits: int = Field(default=0, ge=0)
    average_visit_duration_seconds: Optional[float] = None
    total_visit_duration_seconds: float = Field(default=0.0, ge=0.0)


class VisitorDailyAnalyticsListResponse(PrivacyValidatedModel):
    """List of daily analytics records for a visitor."""
    visitor_id: str
    venue_id: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    days: List[VisitorDailyAnalyticsItem] = Field(default_factory=list)


# ============================================================================
# Visitor Timeline Analytics
# ============================================================================

class VisitorTimelineVisitItem(PrivacyValidatedModel):
    """Single visit within a daily timeline."""
    visit_id: str
    entry_time: str
    exit_time: Optional[str] = None
    entry_gate: str
    exit_gate: Optional[str] = None
    duration_seconds: Optional[float] = None
    status: str


class VisitorTimelineDayItem(PrivacyValidatedModel):
    """Daily aggregated timeline node preserving distinct multiple visits."""
    date: str = Field(..., description="UTC date string (YYYY-MM-DD)")
    entries_count: int = Field(default=0, ge=0)
    exits_count: int = Field(default=0, ge=0)
    visits_count: int = Field(default=0, ge=0)
    total_duration_seconds: float = Field(default=0.0, ge=0.0)
    first_event_time: Optional[str] = None
    last_event_time: Optional[str] = None
    visits: List[VisitorTimelineVisitItem] = Field(default_factory=list)


class VisitorTimelineResponse(PrivacyValidatedModel):
    """Full chronological daily movement timeline."""
    visitor_id: str
    venue_id: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    timeline: List[VisitorTimelineDayItem] = Field(default_factory=list)


# ============================================================================
# Venue-Level Visitor Analytics
# ============================================================================

class VenueVisitorAnalyticsResponse(PrivacyValidatedModel):
    """Venue-wide aggregated visitor analytics for a date range."""
    venue_id: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    unique_visitors: int = Field(default=0, ge=0)
    new_visitors: int = Field(
        default=0,
        ge=0,
        description="Visitors whose first-ever recorded event falls inside the requested date range",
    )
    returning_visitors: int = Field(
        default=0,
        ge=0,
        description="Visitors active in date range whose first-ever recorded event was before start_time",
    )
    total_entries: int = Field(default=0, ge=0)
    total_exits: int = Field(default=0, ge=0)
    total_visits: int = Field(default=0, ge=0)
    completed_visits: int = Field(default=0, ge=0)
    open_visits: int = Field(default=0, ge=0)
    average_visit_duration_seconds: Optional[float] = None
    minimum_visit_duration_seconds: Optional[float] = None
    maximum_visit_duration_seconds: Optional[float] = None
    total_visit_duration_seconds: float = Field(default=0.0, ge=0.0)


class VenueDailyTrendItem(PrivacyValidatedModel):
    """Daily venue-level trend node."""
    date: str = Field(..., description="UTC date string (YYYY-MM-DD)")
    unique_visitors: int = Field(default=0, ge=0)
    total_entries: int = Field(default=0, ge=0)
    total_exits: int = Field(default=0, ge=0)
    total_visits: int = Field(default=0, ge=0)
    completed_visits: int = Field(default=0, ge=0)
    open_visits: int = Field(default=0, ge=0)
    average_visit_duration_seconds: Optional[float] = None
    total_visit_duration_seconds: float = Field(default=0.0, ge=0.0)


class VenueDailyTrendsResponse(PrivacyValidatedModel):
    """Chronological daily visitor trends for a venue."""
    venue_id: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    trends: List[VenueDailyTrendItem] = Field(default_factory=list)


class VenueAnalyticsSummaryResponse(PrivacyValidatedModel):
    """Consolidated venue-level analytics summary."""
    overview: VenueVisitorAnalyticsResponse
    gate_analytics: VisitorGateAnalyticsResponse
    duration_analytics: VisitorDurationAnalyticsResponse
    daily_trends: List[VenueDailyTrendItem] = Field(default_factory=list)

# Sprint 10 — Database & MongoDB Persistence Layer

## 1. Overview
Sprint 10 introduces the official asynchronous MongoDB persistence layer for the CrowdOS FastAPI backend. It persists crucial operational history (Venues, Monitoring Sessions, Movement Events, Alerts, Predictions, and Session Summaries) while preserving the in-memory AI Engine architecture (Sprint 1–8) as the authoritative live state and computation layer.

---

## 2. Architecture & Data Flow

```
Camera / Ingest
      ↓
FastAPI Endpoints (v1)
      ↓
Service Layer (VenueService, SessionService, EventService, PredictionService)
      │
      ├──────────────────────────────────────────┐
      ▼                                          ▼
VenueEngineRegistry (In-Memory)         Repository Layer (Async)
- MovementEngine (Sprint 6)             - VenueRepository
- EventIntelligenceEngine (Sprint 7)    - SessionRepository
- PredictionEngine (Sprint 8)           - EventRepository
                                        - AlertRepository
                                        - PredictionRepository
                                                 │
                                                 ▼
                                        MongoDB (Motor Driver)
                                        - Database: crowdos_db
```

---

## 3. Database Collections & Document Schemas

### 1. `venues` Collection
Persists registered physical venues and configured capacities.
- `_id`: String (`venue_id`)
- `venue_id`: `str` (unique indexed)
- `name`: `str`
- `capacity`: `int` (default: 1000)
- `description`: `Optional[str]`
- `metadata`: `Dict[str, Any]`
- `is_active`: `bool`
- `created_at`: `datetime` (UTC)
- `updated_at`: `datetime` (UTC)

### 2. `sessions` Collection
Persists continuous crowd monitoring sessions and state transitions.
- `_id`: String (`session_id`)
- `session_id`: `str` (unique indexed)
- `venue_id`: `str` (indexed)
- `status`: `str` (`CREATED`, `ACTIVE`, `PAUSED`, `STOPPED`, `EXPIRED`)
- `started_at`: `Optional[str]` (ISO 8601)
- `paused_at`: `Optional[str]` (ISO 8601)
- `resumed_at`: `Optional[str]` (ISO 8601)
- `stopped_at`: `Optional[str]` (ISO 8601)
- `expired_at`: `Optional[str]` (ISO 8601)
- `max_duration_seconds`: `float`
- `metadata`: `Dict[str, Any]`
- `summary`: `Optional[Dict[str, Any]]` (Sprint 7 SessionSummary upon stop)
- `created_at`: `datetime` (UTC)
- `updated_at`: `datetime` (UTC)

### 3. `events` Collection
Persists operational ENTRY and EXIT telemetry records.
- `_id`: String (`event_id`)
- `event_id`: `str` (unique indexed)
- `venue_id`: `str` (indexed)
- `session_id`: `str` (indexed)
- `event_type`: `str` (`ENTRY` or `EXIT`)
- `gate_id`: `str` (indexed)
- `camera_id`: `Optional[str]`
- `track_id`: `Optional[str]` (anonymous tracking reference)
- `detection_id`: `Optional[str]`
- `dwell_time`: `Optional[float]` (seconds for EXIT events)
- `status`: `str` (`processed`, `suppressed`, `error`)
- `source`: `str` (e.g. `TRACK_CROSSING`)
- `created_at`: `datetime` (UTC)
- `updated_at`: `datetime` (UTC)

### 4. `alerts` Collection
Persists operational crowd alerts and anomaly signals.
- `_id`: String (`alert_id`)
- `alert_id`: `str` (unique indexed)
- `session_id`: `str` (indexed)
- `venue_id`: `str` (indexed)
- `gate_id`: `Optional[str]`
- `type`: `str` (e.g. `SURGE`, `CAPACITY_EXCEEDED`, `GATE_IMBALANCE`)
- `severity`: `str` (`INFO`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
- `status`: `str` (`ACTIVE`, `RESOLVED`)
- `message`: `Optional[str]`
- `created_at_iso`: `str`
- `last_seen_iso`: `str`
- `resolved_at_iso`: `Optional[str]`
- `created_at`: `datetime` (UTC)
- `updated_at`: `datetime` (UTC)

### 5. `predictions` Collection
Persists evaluated predictive crowd risk snapshots and forecasts.
- `prediction_id`: `str` (unique UUID)
- `session_id`: `str` (indexed)
- `venue_id`: `str` (indexed)
- `timestamp`: `str` (ISO 8601)
- `risk_score`: `float` (0.0 to 100.0)
- `risk_level`: `str` (`LOW`, `GUARDED`, `ELEVATED`, `HIGH`, `CRITICAL`)
- `factors`: `List[Dict[str, Any]]` (explainable risk contributions)
- `trend_direction`: `str` (`INCREASING`, `STABLE`, `DECREASING`, `INSUFFICIENT_DATA`)
- `trend_slope`: `Optional[float]`
- `trend_confidence`: `str` (`LOW`, `MEDIUM`, `HIGH`, `INSUFFICIENT_DATA`)
- `occupancy_forecast`: `Optional[Dict[str, Any]]` (5m, 10m, 15m horizons)
- `flow_forecast`: `Optional[Dict[str, Any]]`
- `primary_recommendation`: `str`
- `recommendations`: `List[str]`
- `processing_time_ms`: `float`
- `created_at`: `datetime` (UTC)

---

## 4. MongoDB Indexes

Created idempotently upon application startup (`create_all_indexes()`):

| Collection | Index Fields | Properties | Purpose |
|---|---|---|---|
| `venues` | `[("venue_id", ASC)]` | `unique=True` | Fast venue resolution |
| `venues` | `[("created_at", DESC)]` | - | Recent venue listing |
| `sessions` | `[("session_id", ASC)]` | `unique=True` | Fast session lookup |
| `sessions` | `[("venue_id", ASC), ("status", ASC)]` | Compound | Active/scoped session queries |
| `sessions` | `[("created_at", DESC)]` | - | Session history sorting |
| `events` | `[("event_id", ASC)]` | `unique=True` | Duplicate event protection |
| `events` | `[("venue_id", ASC), ("session_id", ASC), ("timestamp", DESC)]` | Compound | Time-range event queries |
| `events` | `[("gate_id", ASC), ("timestamp", DESC)]` | Compound | Per-gate telemetry analysis |
| `alerts` | `[("alert_id", ASC)]` | `unique=True` | Fast alert lookup |
| `alerts` | `[("venue_id", ASC), ("session_id", ASC), ("status", ASC)]` | Compound | Active alert filtering |
| `predictions` | `[("prediction_id", ASC)]` | `unique=True` | Fast snapshot lookup |
| `predictions` | `[("venue_id", ASC), ("session_id", ASC), ("timestamp", DESC)]` | Compound | Risk history retrieval |

---

## 5. Privacy & Security Guarantees

1. **Zero Biometric Persistence**: An automated Pydantic model validator on `EventDBModel` explicitly rejects any payload containing:
   - `embedding`, `face_embedding`, `biometric_vector`, `raw_vector`
   - `face_crop`, `face_image`, `raw_frame`, `raw_video`, `identity_token`
2. **Credential Security**:
   - MongoDB credentials are read exclusively from environment variables (`MONGODB_URL` or `CROWDOS_MONGODB_URL`).
   - Connection logs mask all passwords (e.g. `mongodb://user:***@host:27017`).
   - No credentials appear in git history or logs.

---

## 6. Resilience & Degraded Mode

- If MongoDB is unreachable on startup or encounters a network partition:
  - Connection ping fails gracefully and logs a structured warning.
  - `db_connection.is_connected` returns `False`.
  - The service operates seamlessly in in-memory degraded mode.
  - Live AI Engine calculations and API responses continue without interruption.

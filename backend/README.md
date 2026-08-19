# CrowdOS Backend Service

The FastAPI backend and AI Engine Integration Layer for CrowdOS.

## Overview

The `backend` service provides REST endpoints that interface directly with the in-memory AI Engine (Sprints 1–8). It exposes session management, real-time intelligence queries (flow, occupancy, density, dwell, alerts), predictive risk & decision recommendations, and event ingestion.

## Architecture

```
[REST Clients / UI]
        │ (HTTP / JSON)
        ▼
[FastAPI Endpoints (app/api/v1/endpoints/)]
        │
[Service Layer (app/services/)]
        │
[AI Engine Adapter (app/services/ai_engine_adapter.py)]
        │ (In-memory bridge)
        ▼
[AI Engine (Sprints 1–8)]
  ├── Sprint 6: Movement & Occupancy State
  ├── Sprint 7: Intelligence Engine & Session Manager
  └── Sprint 8: Predictive Crowd Risk & Decision Engine
```

## API Endpoint Categories

| Route Prefix | Description |
|---|---|
| `/` | Root information & status |
| `/health` | Service health probe |
| `/api/status` | System component status |
| `/api/v1/venues` | Venue registry management |
| `/api/v1/venues/{venue_id}/sessions` | Monitoring session lifecycle (`create`, `start`, `pause`, `resume`, `stop`) |
| `/api/v1/venues/{venue_id}/sessions/{session_id}/events` | Movement event ingest (`ENTRY`, `EXIT`) |
| `/api/v1/venues/{venue_id}/intelligence` | Real-time crowd intelligence (flow, occupancy, density, dwell) |
| `/api/v1/venues/{venue_id}/predictions` | Short-horizon predictive risk, trend, decisions, forecasts |
| `/api/v1/venues/{venue_id}/alerts` | Active and historical alerts |

## Privacy Guarantees

The backend adheres to strict enterprise privacy constraints:
- **Zero raw biometric storage:** Face images, crops, embeddings, and biometric vectors are strictly prohibited from all API models.
- **Allowlist Pydantic Schemas:** Only non-identifying operational crowd metrics are serialized and exposed.

## Running Tests

From `backend/`:
```bash
pytest tests/ -v
```

"""
Sprint 10 — Privacy Persistence Audit Tests.

Guarantees that face embeddings, biometric vectors, face crops, raw frames,
and identity tokens are strictly rejected and NEVER stored in MongoDB.
"""
import pytest
from pydantic import ValidationError
from app.models.event import EventDBModel, PROHIBITED_BIOMETRIC_FIELDS
from app.database.mongodb.connection import db_connection


def test_event_db_model_rejects_biometric_fields():
    """Verify EventDBModel explicitly raises ValueError when biometric fields are present."""
    base_data = {
        "event_id": "priv_001",
        "venue_id": "priv_venue",
        "session_id": "priv_sess",
        "event_type": "ENTRY",
        "gate_id": "gate_1",
        "timestamp": "2026-08-26T12:00:00Z",
    }

    # Verify every prohibited field triggers a privacy violation error
    for prohibited in PROHIBITED_BIOMETRIC_FIELDS:
        payload = dict(base_data)
        payload[prohibited] = [0.12, 0.45, 0.99]  # mock embedding/vector
        with pytest.raises(ValidationError) as exc_info:
            EventDBModel(**payload)
        assert "PRIVACY VIOLATION" in str(exc_info.value)


@pytest.mark.asyncio
async def test_mongodb_contains_zero_biometric_keys(async_client):
    """
    Perform a complete recursive scan on all persisted MongoDB documents
    to ensure ZERO biometric keys exist in the database.
    """
    venue_id = "privacy_audit_venue"

    # Ingest full flow
    sess_res = await async_client.post(
        f"/api/v1/venues/{venue_id}/sessions",
        json={"venue_capacity": 1000},
    )
    session_id = sess_res.json()["session_id"]
    await async_client.post(f"/api/v1/venues/{venue_id}/sessions/{session_id}/start")

    # Ingest event
    await async_client.post(
        f"/api/v1/venues/{venue_id}/sessions/{session_id}/events",
        json={"event_type": "ENTRY", "gate_id": "gate_priv"},
    )

    # Ingest exit
    await async_client.post(
        f"/api/v1/venues/{venue_id}/sessions/{session_id}/events",
        json={"event_type": "EXIT", "gate_id": "gate_priv", "dwell_time": 45.0},
    )

    # Trigger prediction
    await async_client.get(f"/api/v1/venues/{venue_id}/predictions")

    # Audit all collections in MongoDB
    db = db_connection.db
    for coll_name in ["venues", "sessions", "events", "alerts", "predictions", "visitors", "visitor_events", "visits"]:
        docs = await db[coll_name].find().to_list(100)
        for doc in docs:
            _assert_no_biometrics_recursive(doc)


def _assert_no_biometrics_recursive(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            current_path = f"{path}.{k}" if path else k
            assert k.lower() not in PROHIBITED_BIOMETRIC_FIELDS, f"Prohibited biometric field found at: {current_path}"
            _assert_no_biometrics_recursive(v, current_path)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _assert_no_biometrics_recursive(item, f"{path}[{idx}]")

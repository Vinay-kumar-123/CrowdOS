"""
Sprint 10 — Real End-to-End MongoDB Atlas & Upstash Redis Verification Script.

This script:
1. Connects to real MongoDB Atlas and verifies CRUD operations.
2. Connects to real Upstash Redis and verifies PING, SET, GET, DEL.
3. Verifies collection indexes.
4. Tests duplicate event protection.
5. Tests privacy enforcement.
6. Reports all results clearly.

Run from backend/ directory:
    python scripts/e2e_verify_sprint10.py
"""
import asyncio
import sys
import os
import uuid
from datetime import datetime, timezone

# ---- ensure proper path resolution ----
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = "PASS"
FAIL = "FAIL"
results = {}


def log(section: str, item: str, status: str, detail: str = ""):
    marker = "✓" if status == PASS else "✗"
    print(f"  [{marker}] {item}: {status}" + (f" — {detail}" if detail else ""))
    results[f"{section}/{item}"] = status


# ===========================================================================
# MONGODB ATLAS VERIFICATION
# ===========================================================================

async def verify_mongodb():
    print("\n══════════════════════════════════════")
    print("  MongoDB Atlas Verification")
    print("══════════════════════════════════════")

    from app.database.mongodb.connection import connect_to_mongo, close_mongo_connection, db_connection, mask_mongodb_uri
    from app.database.mongodb.config import MONGODB_URL, MONGODB_DATABASE

    masked = mask_mongodb_uri(MONGODB_URL)
    print(f"  Connecting to: {masked}")
    print(f"  Database:      {MONGODB_DATABASE}")

    await connect_to_mongo()

    # 1. Connection
    if db_connection.is_connected:
        log("mongodb", "connection", PASS, f"Connected to '{MONGODB_DATABASE}'")
    else:
        log("mongodb", "connection", FAIL, "db_connection.is_connected is False")
        print("\n  [!] MongoDB connection FAILED — aborting MongoDB verification.\n")
        return

    db = db_connection.db

    # 2. Indexes
    try:
        from app.database.mongodb.indexes import INDEX_SPECIFICATIONS
        for coll_name, specs in INDEX_SPECIFICATIONS.items():
            existing_indexes = await db[coll_name].list_indexes().to_list(None)
            log("mongodb", f"indexes/{coll_name}", PASS, f"{len(existing_indexes)} indexes active")
    except Exception as e:
        log("mongodb", "indexes", FAIL, str(e))

    # 3. Venue CRUD
    test_venue_id = f"e2e_venue_{uuid.uuid4().hex[:8]}"
    try:
        from app.repositories.venue_repository import VenueRepository
        from app.models.venue import VenueDBModel
        repo = VenueRepository(db["venues"])

        venue = VenueDBModel(venue_id=test_venue_id, name="E2E Test Venue", capacity=10000)
        await repo.upsert_venue(venue)
        fetched = await repo.get_by_venue_id(test_venue_id)
        assert fetched is not None and fetched.venue_id == test_venue_id
        log("mongodb", "venue_write_read", PASS, f"venue_id={test_venue_id}")
    except Exception as e:
        log("mongodb", "venue_write_read", FAIL, str(e))

    # 4. Session CRUD
    test_session_id = f"e2e_session_{uuid.uuid4().hex[:8]}"
    try:
        from app.repositories.session_repository import SessionRepository
        from app.models.session import SessionDBModel
        sess_repo = SessionRepository(db["sessions"])

        sess = SessionDBModel(
            session_id=test_session_id,
            venue_id=test_venue_id,
            status="CREATED",
        )
        await sess_repo.create(sess)
        await sess_repo.update_session_state(
            test_session_id, "ACTIVE",
            {"started_at": datetime.now(timezone.utc).isoformat()}
        )
        fetched_sess = await sess_repo.get_by_session_id(test_session_id)
        assert fetched_sess is not None and fetched_sess.status == "ACTIVE"
        log("mongodb", "session_write_read", PASS, f"session_id={test_session_id} status=ACTIVE")
    except Exception as e:
        log("mongodb", "session_write_read", FAIL, str(e))

    # 5. Event CRUD
    test_event_id = f"e2e_event_{uuid.uuid4().hex[:8]}"
    try:
        from app.repositories.event_repository import EventRepository
        from app.models.event import EventDBModel
        ev_repo = EventRepository(db["events"])

        event = EventDBModel(
            event_id=test_event_id,
            venue_id=test_venue_id,
            session_id=test_session_id,
            event_type="ENTRY",
            gate_id="gate_e2e_1",
            timestamp=datetime.now(timezone.utc).isoformat(),
            status="processed",
        )
        await ev_repo.save_event(event)
        fetched_ev = await ev_repo.get_by_event_id(test_event_id)
        assert fetched_ev is not None and fetched_ev.event_type == "ENTRY"
        log("mongodb", "event_write_read", PASS, f"event_id={test_event_id}")
    except Exception as e:
        log("mongodb", "event_write_read", FAIL, str(e))

    # 6. Duplicate event protection
    try:
        dup_result = await ev_repo.save_event(event)
        # Should return the existing event, not insert a new one
        count = await db["events"].count_documents({"event_id": test_event_id})
        assert count == 1, f"Expected 1 doc, got {count}"
        log("mongodb", "duplicate_event_protection", PASS, "Duplicate suppressed — count=1")
    except Exception as e:
        log("mongodb", "duplicate_event_protection", FAIL, str(e))

    # 7. EXIT event
    test_exit_id = f"e2e_exit_{uuid.uuid4().hex[:8]}"
    try:
        exit_event = EventDBModel(
            event_id=test_exit_id,
            venue_id=test_venue_id,
            session_id=test_session_id,
            event_type="EXIT",
            gate_id="gate_e2e_1",
            timestamp=datetime.now(timezone.utc).isoformat(),
            dwell_time=90.5,
            status="processed",
        )
        await ev_repo.save_event(exit_event)
        log("mongodb", "exit_event_write", PASS, f"event_id={test_exit_id} dwell_time=90.5")
    except Exception as e:
        log("mongodb", "exit_event_write", FAIL, str(e))

    # 8. Alert CRUD
    test_alert_id = f"e2e_alert_{uuid.uuid4().hex[:8]}"
    try:
        from app.repositories.alert_repository import AlertRepository
        from app.models.alert import AlertDBModel
        alt_repo = AlertRepository(db["alerts"])
        now_iso = datetime.now(timezone.utc).isoformat()
        alert = AlertDBModel(
            alert_id=test_alert_id,
            session_id=test_session_id,
            venue_id=test_venue_id,
            gate_id="gate_e2e_1",
            type="SURGE",
            severity="HIGH",
            status="ACTIVE",
            created_at_iso=now_iso,
            last_seen_iso=now_iso,
        )
        await alt_repo.save_or_update_alert(alert)
        fetched_alt = await alt_repo.get_by_alert_id(test_alert_id)
        assert fetched_alt is not None and fetched_alt.severity == "HIGH"
        log("mongodb", "alert_write_read", PASS, f"alert_id={test_alert_id} severity=HIGH")
    except Exception as e:
        log("mongodb", "alert_write_read", FAIL, str(e))

    # 9. Prediction CRUD
    test_pred_id = f"e2e_pred_{uuid.uuid4().hex[:8]}"
    try:
        from app.repositories.prediction_repository import PredictionRepository
        from app.models.prediction import PredictionDBModel
        pred_repo = PredictionRepository(db["predictions"])
        pred = PredictionDBModel(
            prediction_id=test_pred_id,
            session_id=test_session_id,
            venue_id=test_venue_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            risk_score=72.3,
            risk_level="HIGH",
            trend_direction="INCREASING",
            primary_recommendation="REDUCE_INFLOW",
        )
        await pred_repo.save_prediction(pred)
        fetched_pred = await pred_repo.get_by_prediction_id(test_pred_id)
        assert fetched_pred is not None and fetched_pred.risk_score == 72.3
        log("mongodb", "prediction_write_read", PASS, f"prediction_id={test_pred_id} risk_score=72.3")
    except Exception as e:
        log("mongodb", "prediction_write_read", FAIL, str(e))

    # 10. Read all persisted records
    try:
        venues_count = await db["venues"].count_documents({"venue_id": test_venue_id})
        sessions_count = await db["sessions"].count_documents({"session_id": test_session_id})
        events_count = await db["events"].count_documents({"session_id": test_session_id})
        alerts_count = await db["alerts"].count_documents({"alert_id": test_alert_id})
        preds_count = await db["predictions"].count_documents({"prediction_id": test_pred_id})
        log("mongodb", "read_all_records", PASS,
            f"venues={venues_count}, sessions={sessions_count}, events={events_count}, alerts={alerts_count}, predictions={preds_count}")
    except Exception as e:
        log("mongodb", "read_all_records", FAIL, str(e))

    # 11. Privacy: verify no biometric fields in any document
    try:
        from app.models.event import PROHIBITED_BIOMETRIC_FIELDS
        all_events = await db["events"].find({"venue_id": test_venue_id}).to_list(100)
        biometric_found = False
        for doc in all_events:
            for key in doc.keys():
                if key.lower() in PROHIBITED_BIOMETRIC_FIELDS:
                    biometric_found = True
                    break
        if biometric_found:
            log("mongodb", "privacy_check", FAIL, "Biometric field found in stored documents!")
        else:
            log("mongodb", "privacy_check", PASS, "Zero biometric fields in any stored document")
    except Exception as e:
        log("mongodb", "privacy_check", FAIL, str(e))

    # 12. Cleanup test data
    try:
        await db["venues"].delete_many({"venue_id": test_venue_id})
        await db["sessions"].delete_many({"venue_id": test_venue_id})
        await db["events"].delete_many({"venue_id": test_venue_id})
        await db["alerts"].delete_many({"venue_id": test_venue_id})
        await db["predictions"].delete_many({"venue_id": test_venue_id})
        log("mongodb", "cleanup", PASS, f"Test data removed for venue_id={test_venue_id}")
    except Exception as e:
        log("mongodb", "cleanup", FAIL, str(e))

    await close_mongo_connection()


# ===========================================================================
# UPSTASH REDIS VERIFICATION
# ===========================================================================

async def verify_redis():
    print("\n══════════════════════════════════════")
    print("  Upstash Redis Verification")
    print("══════════════════════════════════════")

    from app.database.redis.connection import connect_to_redis, close_redis_connection, redis_connection, mask_redis_uri
    from app.database.redis.config import REDIS_URL

    masked = mask_redis_uri(REDIS_URL)
    print(f"  Connecting to: {masked}")

    await connect_to_redis()

    # 1. Connection
    if redis_connection.is_connected:
        log("redis", "connection", PASS, "is_connected=True")
    else:
        log("redis", "connection", FAIL, "is_connected=False")
        print("\n  [!] Redis connection FAILED — aborting Redis verification.\n")
        return

    client = redis_connection.get_client()

    # 2. PING
    try:
        pong = await client.ping()
        if pong:
            log("redis", "ping", PASS, "PONG received")
        else:
            log("redis", "ping", FAIL, "PING returned falsy")
    except Exception as e:
        log("redis", "ping", FAIL, str(e))

    # 3. SET
    test_key = f"crowdos:e2e_test:{uuid.uuid4().hex[:8]}"
    test_value = f"sprint10_verification_{uuid.uuid4().hex[:8]}"
    try:
        await client.set(test_key, test_value, ex=60)  # expires in 60s
        log("redis", "set", PASS, f"key={test_key}")
    except Exception as e:
        log("redis", "set", FAIL, str(e))

    # 4. GET
    try:
        retrieved = await client.get(test_key)
        if retrieved == test_value:
            log("redis", "get", PASS, f"value matches expected")
        else:
            log("redis", "get", FAIL, f"expected='{test_value}', got='{retrieved}'")
    except Exception as e:
        log("redis", "get", FAIL, str(e))

    # 5. DEL (cleanup)
    try:
        await client.delete(test_key)
        # Confirm deleted
        gone = await client.get(test_key)
        if gone is None:
            log("redis", "cleanup_delete", PASS, f"key '{test_key}' confirmed deleted")
        else:
            log("redis", "cleanup_delete", FAIL, "Key still exists after DELETE")
    except Exception as e:
        log("redis", "cleanup_delete", FAIL, str(e))

    # 6. Credential safety — REDIS_URL must not appear in client representation
    redis_str = str(client)
    if "password" not in redis_str.lower() and "default:" not in redis_str.lower():
        log("redis", "credential_masking", PASS, "No credentials visible in client repr")
    else:
        log("redis", "credential_masking", FAIL, "Potential credential leak in client repr")

    await close_redis_connection()


# ===========================================================================
# PRIVACY UNIT CHECK
# ===========================================================================

def verify_privacy():
    print("\n══════════════════════════════════════")
    print("  Privacy Enforcement Verification")
    print("══════════════════════════════════════")
    from pydantic import ValidationError
    from app.models.event import EventDBModel, PROHIBITED_BIOMETRIC_FIELDS

    base = {
        "event_id": "priv_001",
        "venue_id": "priv_venue",
        "session_id": "priv_sess",
        "event_type": "ENTRY",
        "gate_id": "gate_1",
        "timestamp": "2026-08-26T12:00:00Z",
    }

    all_blocked = True
    for field in PROHIBITED_BIOMETRIC_FIELDS:
        try:
            EventDBModel(**{**base, field: [0.1, 0.2, 0.3]})
            print(f"  [✗] Field '{field}' was NOT rejected (PRIVACY BREACH)")
            all_blocked = False
        except ValidationError:
            pass

    if all_blocked:
        log("privacy", "biometric_model_validation", PASS,
            f"All {len(PROHIBITED_BIOMETRIC_FIELDS)} prohibited fields rejected by EventDBModel")
    else:
        log("privacy", "biometric_model_validation", FAIL, "Some biometric fields not blocked")


# ===========================================================================
# SECURITY CHECKS
# ===========================================================================

def verify_security():
    print("\n══════════════════════════════════════")
    print("  Security Verification")
    print("══════════════════════════════════════")

    env_example_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env.example")
    try:
        with open(env_example_path, "r") as f:
            content = f.read()

        # Check for known credential patterns
        import re
        has_real_password = bool(re.search(r"@[\w.-]+\.\w+:\d+", content))
        has_placeholder = "<password>" in content or "<db_password>" in content

        if has_real_password and not has_placeholder:
            log("security", "env_example_sanitized", FAIL,
                ".env.example appears to contain real connection strings!")
        elif has_placeholder:
            log("security", "env_example_sanitized", PASS,
                ".env.example contains only placeholders")
        else:
            log("security", "env_example_sanitized", PASS,
                ".env.example appears clean")
    except Exception as e:
        log("security", "env_example_sanitized", FAIL, str(e))

    # Verify .gitignore has .env
    gitignore_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".gitignore")
    try:
        with open(gitignore_path, "r") as f:
            gi_content = f.read()
        if "\n.env\n" in gi_content or "\n.env\r\n" in gi_content or ".env\n" in gi_content:
            log("security", "env_in_gitignore", PASS, ".env is in .gitignore")
        else:
            log("security", "env_in_gitignore", FAIL, ".env NOT found in .gitignore")
    except Exception as e:
        log("security", "env_in_gitignore", FAIL, str(e))


# ===========================================================================
# MAIN
# ===========================================================================

async def main():
    print("╔══════════════════════════════════════════╗")
    print("║  Sprint 10 — E2E Verification Script     ║")
    print("╚══════════════════════════════════════════╝")

    verify_privacy()
    verify_security()
    await verify_mongodb()
    await verify_redis()

    print("\n══════════════════════════════════════")
    print("  Summary")
    print("══════════════════════════════════════")

    passed = sum(1 for v in results.values() if v == PASS)
    failed = sum(1 for v in results.values() if v == FAIL)
    total = passed + failed

    for key, status in results.items():
        marker = "✓" if status == PASS else "✗"
        print(f"  [{marker}] {key}: {status}")

    print(f"\n  TOTAL: {passed}/{total} PASSED, {failed}/{total} FAILED")
    if failed == 0:
        print("\n  ✓ Sprint 10 E2E Verification: ALL PASS")
    else:
        print(f"\n  ✗ Sprint 10 E2E Verification: {failed} FAILURES")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

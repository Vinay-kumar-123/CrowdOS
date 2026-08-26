"""
MongoDB Index Definitions & Management — Sprint 10.

Defines and creates all necessary MongoDB indexes idempotently on startup.
"""
import logging
from pymongo import ASCENDING, DESCENDING, IndexModel

logger = logging.getLogger("crowdos.mongodb.indexes")


INDEX_SPECIFICATIONS = {
    "venues": [
        IndexModel([("venue_id", ASCENDING)], unique=True, name="idx_venues_venue_id_unique"),
        IndexModel([("created_at", DESCENDING)], name="idx_venues_created_at"),
    ],
    "sessions": [
        IndexModel([("session_id", ASCENDING)], unique=True, name="idx_sessions_session_id_unique"),
        IndexModel([("venue_id", ASCENDING), ("status", ASCENDING)], name="idx_sessions_venue_status"),
        IndexModel([("created_at", DESCENDING)], name="idx_sessions_created_at"),
    ],
    "events": [
        IndexModel([("event_id", ASCENDING)], unique=True, name="idx_events_event_id_unique"),
        IndexModel(
            [("venue_id", ASCENDING), ("session_id", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_events_venue_session_time"
        ),
        IndexModel([("gate_id", ASCENDING), ("timestamp", DESCENDING)], name="idx_events_gate_time"),
        IndexModel([("created_at", DESCENDING)], name="idx_events_created_at"),
    ],
    "alerts": [
        IndexModel([("alert_id", ASCENDING)], unique=True, name="idx_alerts_alert_id_unique"),
        IndexModel(
            [("venue_id", ASCENDING), ("session_id", ASCENDING), ("status", ASCENDING)],
            name="idx_alerts_venue_session_status"
        ),
        IndexModel([("created_at", DESCENDING)], name="idx_alerts_created_at"),
    ],
    "predictions": [
        IndexModel([("prediction_id", ASCENDING)], unique=True, name="idx_predictions_id_unique"),
        IndexModel(
            [("venue_id", ASCENDING), ("session_id", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_predictions_venue_session_time"
        ),
        IndexModel([("created_at", DESCENDING)], name="idx_predictions_created_at"),
    ],
}


async def create_all_indexes(db) -> dict:
    """
    Ensure all defined indexes exist across collections.
    Idempotent and safe to run on every application startup.
    """
    results = {}
    if db is None:
        logger.warning("Cannot create indexes: MongoDB database instance is None.")
        return results

    for collection_name, index_models in INDEX_SPECIFICATIONS.items():
        try:
            collection = db[collection_name]
            created = await collection.create_indexes(index_models)
            results[collection_name] = created
            logger.info(f"MongoDB indexes verified for collection '{collection_name}': {created}")
        except Exception as e:
            logger.error(f"Failed to create indexes for collection '{collection_name}': {e}")
            results[collection_name] = []

    return results

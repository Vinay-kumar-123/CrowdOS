"""
Camera Credential Encryption Key Migration CLI — Sprint 17.

Rotates the AES-256-GCM encryption key for camera credentials stored in MongoDB.

Usage:
    python backend/scripts/migrate_camera_keys.py \\
        --old-key "<old_camera_encryption_key>" \\
        --new-key "<new_camera_encryption_key>" \\
        [--mongo-uri "<mongo_uri>"] \\
        [--mongo-db "<mongo_db_name>"] \\
        [--dry-run]

Security Guarantees:
    - Never prints plaintext credentials or raw key values to console/logs.
    - Verifies decryption under the old key before re-encrypting.
    - Verifies round-trip decryption under the new key before committing to MongoDB.
    - Atomic document updates per camera.
    - Fails safely if keys are invalid, identical, or decryption fails.
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Tuple

# Add backend directory to sys.path so app imports work when executed directly
_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.camera_security import (
    encrypt_credentials,
    decrypt_credentials,
    sanitize_source_url,
)
from app.core.settings import settings


async def migrate_camera_credentials(
    old_key: str,
    new_key: str,
    mongo_uri: str,
    mongo_db_name: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Core migration logic. Can be invoked programmatically from tests or via CLI.
    """
    if not old_key or not isinstance(old_key, str) or not old_key.strip():
        raise ValueError("old_key must be a non-empty string.")
    if not new_key or not isinstance(new_key, str) or not new_key.strip():
        raise ValueError("new_key must be a non-empty string.")
    if old_key == new_key:
        raise ValueError("old_key and new_key must be different.")

    client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client[mongo_db_name]
    cameras_col = db["cameras"]

    stats = {
        "scanned": 0,
        "migrated": 0,
        "failed": 0,
        "skipped": 0,
        "dry_run": dry_run,
        "errors": [],
    }

    try:
        # Scan all cameras that have credentials_encrypted populated
        cursor = cameras_col.find({"credentials_encrypted": {"$exists": True, "$ne": None}})
        if asyncio.iscoroutine(cursor):
            cursor = await cursor
        async for doc in cursor:

            camera_id = doc.get("camera_id", str(doc.get("_id", "unknown")))
            enc_token = doc.get("credentials_encrypted")
            stats["scanned"] += 1

            if not enc_token:
                stats["skipped"] += 1
                continue

            try:
                # 1. Decrypt with old key
                plaintext = decrypt_credentials(enc_token, old_key)

                # 2. Re-encrypt with new key
                new_token = encrypt_credentials(plaintext, new_key)

                # 3. Verify round-trip with new key
                verified_plaintext = decrypt_credentials(new_token, new_key)
                if verified_plaintext != plaintext:
                    raise RuntimeError("Verification failed: re-encrypted payload round-trip mismatch.")

                # 4. Commit to database if not dry_run
                if not dry_run:
                    now_utc = datetime.now(timezone.utc)
                    await cameras_col.update_one(
                        {"_id": doc["_id"]},
                        {
                            "$set": {
                                "credentials_encrypted": new_token,
                                "updated_at": now_utc,
                            }
                        },
                    )

                stats["migrated"] += 1

            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append({"camera_id": camera_id, "error": str(e)})

    finally:
        client.close()

    return stats


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description="Migrate camera credential encryption from an old key to a new key."
    )
    parser.add_argument(
        "--old-key",
        required=True,
        help="Current CAMERA_ENCRYPTION_KEY used to decrypt stored credentials.",
    )
    parser.add_argument(
        "--new-key",
        required=True,
        help="New CAMERA_ENCRYPTION_KEY to re-encrypt stored credentials.",
    )
    parser.add_argument(
        "--mongo-uri",
        default=getattr(settings, "MONGODB_URL", "mongodb://localhost:27017"),
        help="MongoDB connection URI.",
    )
    parser.add_argument(
        "--mongo-db",
        default=getattr(settings, "MONGODB_DATABASE", "crowdos_dev"),
        help="MongoDB database name.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Test decryption and re-encryption without modifying the database.",
    )
    return parser.parse_args(args)


async def main_async():
    args = parse_args()
    print("=" * 60)
    print("CrowdOS Camera Key Migration Utility")
    print(f"Target Database : {args.mongo_db}")
    print(f"Dry Run Mode    : {args.dry_run}")
    print("=" * 60)

    try:
        stats = await migrate_camera_credentials(
            old_key=args.old_key,
            new_key=args.new_key,
            mongo_uri=args.mongo_uri,
            mongo_db_name=args.mongo_db,
            dry_run=args.dry_run,
        )

        print(f"Total Scanned : {stats['scanned']}")
        print(f"Migrated      : {stats['migrated']}")
        print(f"Skipped       : {stats['skipped']}")
        print(f"Failed        : {stats['failed']}")

        if stats["failed"] > 0:
            print("Migration completed with errors:")
            for err in stats["errors"]:
                print(f"  - Camera {err['camera_id']}: {err['error']}")
            sys.exit(1)
        else:
            print("Migration completed successfully with zero errors.")
            sys.exit(0)

    except Exception as exc:
        print(f"Fatal migration error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main_async())

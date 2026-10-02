"""
Camera Credential Encryption Key Migration CLI — Sprint 17.

Rotates the AES-256-GCM encryption key for camera credentials stored in MongoDB.

Usage (preferred — secure, no secrets in shell history or process table):

    # Via environment variables:
    OLD_CAMERA_ENCRYPTION_KEY=<old> NEW_CAMERA_ENCRYPTION_KEY=<new> \\
        python backend/scripts/migrate_camera_keys.py [--dry-run]

    # Via key files:
    python backend/scripts/migrate_camera_keys.py \\
        --old-key-file /run/secrets/old_camera_key \\
        --new-key-file /run/secrets/new_camera_key \\
        [--dry-run]

    # Via interactive prompt (when no other source is available):
    python backend/scripts/migrate_camera_keys.py [--dry-run]

DEPRECATED (exposes secrets in process listings and shell history — avoid):

    python backend/scripts/migrate_camera_keys.py \\
        --old-key "<old_camera_encryption_key>" \\
        --new-key "<new_camera_encryption_key>"

Key Resolution Order (first match wins):
    1. --old-key-file / --new-key-file flag (reads key from file path)
    2. OLD_CAMERA_ENCRYPTION_KEY / NEW_CAMERA_ENCRYPTION_KEY env vars
    3. CROWDOS_OLD_CAMERA_KEY / CROWDOS_NEW_CAMERA_KEY env vars (legacy aliases)
    4. Interactive getpass prompt (only when stdin is a TTY)
    5. Fail with a clear error message

Deprecation Warning:
    --old-key and --new-key accept secrets directly on the command line.
    This exposes secrets in process listings (ps aux) and shell history.
    Use the options above whenever possible.

Security Guarantees:
    - Never prints plaintext credentials or raw key values to console/logs.
    - Verifies decryption under the old key before re-encrypting.
    - Verifies round-trip decryption under the new key before committing to MongoDB.
    - Atomic document updates per camera.
    - Fails safely if keys are invalid, identical, or decryption fails.
    - Skips documents already migrated to the new key (restart-safe).
"""
import argparse
import asyncio
import getpass
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional

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


def _read_key_from_file(path: str) -> str:
    """Read an encryption key from a file path, stripping surrounding whitespace."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError as exc:
        raise ValueError(f"Cannot read key file '{path}': {exc}") from exc


def resolve_key(
    *,
    cli_arg: Optional[str],
    file_arg: Optional[str],
    env_vars: tuple,
    prompt_name: str,
    deprecated_cli_name: str,
) -> str:
    """
    Resolve an encryption key from the configured sources in priority order.

    Priority:
        1. Key-file flag (--old-key-file / --new-key-file)
        2. Environment variables (first non-empty match)
        3. Interactive getpass prompt (only if stdin is a TTY)

    The --old-key / --new-key CLI flags are still accepted for backward
    compatibility but emit a deprecation warning because secrets passed on
    the command line appear in process listings and shell history.

    Raises ValueError if no source provides a non-empty key.
    """
    # 1. Key file takes highest priority (secure)
    if file_arg:
        key = _read_key_from_file(file_arg)
        if key:
            return key
        raise ValueError(f"Key file '{file_arg}' is empty.")

    # 2. Environment variables
    for env_name in env_vars:
        val = os.environ.get(env_name, "").strip()
        if val:
            return val

    # 3. Deprecated CLI argument — accepted but warned
    if cli_arg and cli_arg.strip():
        print(
            f"[SECURITY WARNING] {deprecated_cli_name} passed as a command-line argument. "
            "This exposes the secret in process listings (ps aux) and shell history. "
            "Use --old-key-file / --new-key-file or environment variables instead.",
            file=sys.stderr,
        )
        return cli_arg.strip()

    # 4. Interactive prompt (TTY only)
    if sys.stdin.isatty():
        try:
            key = getpass.getpass(f"Enter {prompt_name}: ").strip()
            if key:
                return key
            raise ValueError(f"{prompt_name} cannot be empty.")
        except (EOFError, KeyboardInterrupt):
            raise ValueError(f"No {prompt_name} provided (interactive input cancelled).")

    # 5. No source available — fail clearly
    env_list = " / ".join(env_vars)
    raise ValueError(
        f"No {prompt_name} found. Provide it via:\n"
        f"  - {deprecated_cli_name} flag (deprecated)\n"
        f"  - Key file flag\n"
        f"  - Environment variable ({env_list})\n"
        f"  - Interactive prompt (requires a TTY)"
    )


async def migrate_camera_credentials(
    old_key: str,
    new_key: str,
    mongo_uri: str,
    mongo_db_name: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Core migration logic. Can be invoked programmatically from tests or via CLI.

    Restart-safe: documents whose credentials are already decryptable by new_key
    are counted as 'already_migrated' and skipped without modification or error.

    Stats returned:
        scanned          — total documents with credentials_encrypted field
        migrated         — re-encrypted from old_key to new_key this run
        already_migrated — already encrypted under new_key (skipped safely)
        failed           — could not decrypt under either key (or round-trip failed)
        skipped          — documents with empty/missing credentials_encrypted field
        dry_run          — whether changes were committed
        errors           — list of {camera_id, error} dicts for failed records
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

    stats: Dict[str, Any] = {
        "scanned": 0,
        "migrated": 0,
        "already_migrated": 0,
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

            # --- Attempt decryption with old key ---
            plaintext: Optional[str] = None
            old_key_ok = False
            try:
                plaintext = decrypt_credentials(enc_token, old_key)
                old_key_ok = True
            except Exception:
                pass  # Will try new key next

            if old_key_ok and plaintext is not None:
                # Document is still encrypted under old_key — migrate it
                try:
                    # Re-encrypt with new key
                    new_token = encrypt_credentials(plaintext, new_key)

                    # Verify round-trip with new key
                    verified = decrypt_credentials(new_token, new_key)
                    if verified != plaintext:
                        raise RuntimeError(
                            "Verification failed: re-encrypted payload round-trip mismatch."
                        )

                    # Commit to database if not dry_run
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

                except Exception as exc:
                    stats["failed"] += 1
                    stats["errors"].append({"camera_id": camera_id, "error": str(exc)})
                continue

            # --- Old key failed: check if document is already migrated ---
            new_key_ok = False
            try:
                decrypt_credentials(enc_token, new_key)
                new_key_ok = True
            except Exception:
                pass

            if new_key_ok:
                # Already encrypted under new_key — safe to skip (restart-safe)
                stats["already_migrated"] += 1
                continue

            # --- Both keys failed: truly malformed/unreadable record ---
            stats["failed"] += 1
            stats["errors"].append({
                "camera_id": camera_id,
                "error": "Decryption failed with both old_key and new_key (malformed or unknown key).",
            })

    finally:
        client.close()

    return stats


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description=(
            "Migrate camera credential encryption from an old key to a new key.\n\n"
            "Preferred: supply keys via environment variables or key files.\n"
            "Deprecated: --old-key / --new-key expose secrets in process listings."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # --- Secure key input options ---
    parser.add_argument(
        "--old-key-file",
        default=None,
        metavar="PATH",
        help="Path to a file containing the old CAMERA_ENCRYPTION_KEY (recommended).",
    )
    parser.add_argument(
        "--new-key-file",
        default=None,
        metavar="PATH",
        help="Path to a file containing the new CAMERA_ENCRYPTION_KEY (recommended).",
    )

    # --- Deprecated CLI options (kept for backward compatibility) ---
    parser.add_argument(
        "--old-key",
        default=None,
        metavar="KEY",
        help=(
            "[DEPRECATED] Current CAMERA_ENCRYPTION_KEY. "
            "Prefer --old-key-file or OLD_CAMERA_ENCRYPTION_KEY env var."
        ),
    )
    parser.add_argument(
        "--new-key",
        default=None,
        metavar="KEY",
        help=(
            "[DEPRECATED] New CAMERA_ENCRYPTION_KEY. "
            "Prefer --new-key-file or NEW_CAMERA_ENCRYPTION_KEY env var."
        ),
    )

    # --- Connection options ---
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

    # Resolve keys securely
    try:
        old_key = resolve_key(
            cli_arg=args.old_key,
            file_arg=args.old_key_file,
            env_vars=("OLD_CAMERA_ENCRYPTION_KEY", "CROWDOS_OLD_CAMERA_KEY"),
            prompt_name="old CAMERA_ENCRYPTION_KEY",
            deprecated_cli_name="--old-key",
        )
        new_key = resolve_key(
            cli_arg=args.new_key,
            file_arg=args.new_key_file,
            env_vars=("NEW_CAMERA_ENCRYPTION_KEY", "CROWDOS_NEW_CAMERA_KEY"),
            prompt_name="new CAMERA_ENCRYPTION_KEY",
            deprecated_cli_name="--new-key",
        )
    except ValueError as exc:
        print(f"Key resolution error: {exc}", file=sys.stderr)
        sys.exit(2)

    print("=" * 60)
    print("CrowdOS Camera Key Migration Utility")
    print(f"Target Database : {args.mongo_db}")
    print(f"Dry Run Mode    : {args.dry_run}")
    print("=" * 60)

    try:
        stats = await migrate_camera_credentials(
            old_key=old_key,
            new_key=new_key,
            mongo_uri=args.mongo_uri,
            mongo_db_name=args.mongo_db,
            dry_run=args.dry_run,
        )

        print(f"Total Scanned    : {stats['scanned']}")
        print(f"Migrated         : {stats['migrated']}")
        print(f"Already Migrated : {stats['already_migrated']}")
        print(f"Skipped          : {stats['skipped']}")
        print(f"Failed           : {stats['failed']}")

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

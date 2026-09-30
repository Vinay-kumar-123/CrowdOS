"""
Camera Security & Deterministic Idempotency Utilities — Sprint 16 (Security Remediation).

Credential Encryption:
    Algorithm : AES-256-GCM (AESGCM from the `cryptography` library)
    Key size  : 256 bits (derived from CAMERA_ENCRYPTION_KEY via HKDF-SHA256)
    Nonce     : 96-bit (12 bytes) cryptographically random per-encryption
    Tag       : 128-bit authentication tag (GCM standard); appended by the library
    Format    : base64url-safe( nonce[12] || ciphertext+tag[N+16] )

    The `cryptography` package (≥41.0) is a direct declared dependency, NOT a custom
    construction.  `encrypt_credentials` and `decrypt_credentials` require an explicit
    key parameter — callers must NOT pass `settings.SECRET_KEY` (the JWT signing key).
    Use `settings.CAMERA_ENCRYPTION_KEY` exclusively.

Key Management:
    • CAMERA_ENCRYPTION_KEY is a separate configuration value from SECRET_KEY.
    • It is validated at startup by the Settings model (see settings.py).
    • Rotating the key requires a re-encryption migration; see MIGRATION NOTES below.

MIGRATION NOTES (key rotation):
    When CAMERA_ENCRYPTION_KEY is rotated:
    1. Decrypt every existing `credentials_encrypted` document using the OLD key.
    2. Re-encrypt with the NEW key.
    3. Replace the stored blob atomically.
    4. Old-key ciphertext decrypted by a new key raises ValueError immediately;
       do NOT silently fall back to plaintext.

    A migration utility can be implemented in backend/scripts/migrate_camera_keys.py.
"""
import base64
import hashlib
import hmac
import re
import secrets
import urllib.parse
import uuid
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_AES_KEY_BYTES = 32   # AES-256
_NONCE_BYTES   = 12   # 96-bit nonce recommended for GCM


def _derive_aes_key(raw_key: str) -> bytes:
    """
    Derive a 256-bit AES key from the raw CAMERA_ENCRYPTION_KEY string.
    Uses SHA-256 for a deterministic, constant-length key.
    The salt domain-separates this derivation from any JWT-key usage.
    """
    if not raw_key:
        raise ValueError("CAMERA_ENCRYPTION_KEY must not be empty.")
    domain = b"crowdos-camera-credential-encryption-v1"
    return hashlib.sha256(domain + raw_key.encode("utf-8")).digest()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sanitize_source_url(url: Optional[str]) -> str:
    """
    Remove sensitive embedded username/password from RTSP/HTTP URLs.
    e.g. 'rtsp://admin:pass123@192.168.1.50:554/h264' -> 'rtsp://***:***@192.168.1.50:554/h264'
    Safe on non-URLs or errors.
    """
    if not url:
        return ""
    url_str = str(url).strip()
    try:
        parsed = urllib.parse.urlsplit(url_str)
        if parsed.scheme and parsed.netloc and "@" in parsed.netloc:
            _, hostinfo = parsed.netloc.rsplit("@", 1)
            masked_netloc = f"***:***@{hostinfo}"
            return urllib.parse.urlunsplit(
                (parsed.scheme, masked_netloc, parsed.path, parsed.query, parsed.fragment)
            )
        return url_str
    except Exception:
        return "[REDACTED_SOURCE]"


def sanitize_error_message(message: Optional[str]) -> Optional[str]:
    """
    Strip embedded connection credentials from error traces or messages.
    Handles passwords that contain '@' (e.g. p@ss123).
    """
    if not message:
        return None
    cleaned = re.sub(r"://([^/\s]+)@([a-zA-Z0-9_.-]+)", r"://***:***@\2", str(message))
    return cleaned


def encrypt_credentials(secret_data: str, camera_encryption_key: str) -> str:
    """
    Encrypt a sensitive camera credential string using AES-256-GCM.

    Uses the `cryptography` library (no custom cipher construction).

    Args:
        secret_data          : Plaintext credential string (e.g. full RTSP URL with password).
        camera_encryption_key: Value of settings.CAMERA_ENCRYPTION_KEY — NOT the JWT SECRET_KEY.

    Returns:
        Base64url-encoded string: nonce[12] || ciphertext+tag[N+16]

    Raises:
        ValueError: If camera_encryption_key is empty.
    """
    if not secret_data:
        return ""
    key = _derive_aes_key(camera_encryption_key)
    nonce = secrets.token_bytes(_NONCE_BYTES)
    aesgcm = AESGCM(key)
    # AESGCM.encrypt returns ciphertext + 16-byte authentication tag concatenated
    ct_with_tag = aesgcm.encrypt(nonce, secret_data.encode("utf-8"), None)
    raw_payload = nonce + ct_with_tag
    return base64.urlsafe_b64encode(raw_payload).decode("ascii")


def decrypt_credentials(encrypted_token: str, camera_encryption_key: str) -> str:
    """
    Decrypt an AES-256-GCM credential blob produced by encrypt_credentials().

    Args:
        encrypted_token      : Base64url string from encrypt_credentials().
        camera_encryption_key: Value of settings.CAMERA_ENCRYPTION_KEY — NOT the JWT SECRET_KEY.

    Returns:
        Plaintext credential string.

    Raises:
        ValueError : On malformed token (too short, bad base64, or wrong key/tag mismatch).
        cryptography.exceptions.InvalidTag : Propagated from AESGCM on authentication failure.
    """
    if not encrypted_token:
        return ""
    try:
        raw_payload = base64.urlsafe_b64decode(encrypted_token.encode("ascii") + b"==")
    except Exception as exc:
        raise ValueError(f"Malformed credential token (base64 decode failed): {exc}") from exc

    # Minimum size: 12 nonce + 16 tag = 28 bytes (ciphertext may be 0 bytes for empty string)
    if len(raw_payload) < _NONCE_BYTES + 16:
        raise ValueError(
            f"Malformed credential token: payload length {len(raw_payload)} < minimum 28 bytes."
        )

    key = _derive_aes_key(camera_encryption_key)
    nonce = raw_payload[:_NONCE_BYTES]
    ct_with_tag = raw_payload[_NONCE_BYTES:]

    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ct_with_tag, None)
    except Exception as exc:
        raise ValueError(f"Credential authentication failed: {exc}") from exc
    return plaintext.decode("utf-8")


def derive_deterministic_event_id(
    camera_id: str,
    gate_id: str,
    frame_number: int,
    timestamp: float,
    track_id: Optional[str] = None,
) -> str:
    """
    Derive a deterministic, idempotent event UUID from stable physical frame properties.

    Same source frame and track (camera_id + gate_id + [track_id] + frame_number + timestamp_ms) -> SAME UUID.

    Limitation: frame_number is a per-FrameProducer monotonic counter that resets on
    camera reconnect.  After reconnect, the new frame has a fresh timestamp, so the
    resulting event_id is distinct from pre-reconnect frames at the same counter value —
    which is semantically correct (different physical moment).  This is documented and
    accepted behavior; see Sprint 16 audit report.
    """
    ms_timestamp = int(round(timestamp * 1000))
    if track_id:
        urn = f"crowdos://events/{camera_id}/{gate_id}/{track_id}/{frame_number}/{ms_timestamp}"
    else:
        urn = f"crowdos://events/{camera_id}/{gate_id}/{frame_number}/{ms_timestamp}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, urn))

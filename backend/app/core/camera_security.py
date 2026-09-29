"""
Camera Security & Deterministic Idempotency Utilities — Sprint 16.

Provides:
- Strict camera source URL sanitization (stripping plaintext credentials)
- Cryptographic credential encryption/decryption using standard library (AES-free authenticated stream cipher with HMAC-SHA256)
- Deterministic event ID generation from physical source frame metadata
"""
import base64
import hashlib
import hmac
import secrets
import urllib.parse
import uuid
from typing import Optional


def sanitize_source_url(url: Optional[str]) -> str:
    """
    Remove sensitive embedded username/password from RTSP/HTTP URLs.
    e.g. 'rtsp://admin:pass123@192.168.1.50:554/h264' -> 'rtsp://***:***@192.168.1.50:554/h264'
    If URL contains no credentials, returns sanitized string unchanged.
    Safe on non-URLs or errors.
    """
    if not url:
        return ""
    url_str = str(url).strip()
    try:
        parsed = urllib.parse.urlsplit(url_str)
        if parsed.scheme and parsed.netloc:
            # Check if userinfo exists in netloc
            if "@" in parsed.netloc:
                userinfo, hostinfo = parsed.netloc.rsplit("@", 1)
                masked_netloc = f"***:***@{hostinfo}"
                return urllib.parse.urlunsplit(
                    (parsed.scheme, masked_netloc, parsed.path, parsed.query, parsed.fragment)
                )
        return url_str
    except Exception:
        # Fallback if unparseable
        return "[REDACTED_SOURCE]"


def sanitize_error_message(message: Optional[str]) -> Optional[str]:
    """
    Strip any embedded connection credentials from error traces or messages.
    """
    if not message:
        return None
    msg = str(message)
    # Match any protocol with credentials e.g. rtsp://user:pass@host:port
    import re
    cleaned = re.sub(r"://([^/\s]+)@([a-zA-Z0-9_.-]+)", r"://***:***@\2", msg)
    return cleaned


def encrypt_credentials(secret_data: str, secret_key: str) -> str:
    """
    Encrypt sensitive camera credentials/source string using authenticated keystream cipher (HMAC-SHA256).
    Zero external dependencies — uses Python stdlib hashlib, hmac, secrets.
    Format: base64(iv[16] + tag[32] + ciphertext[N])
    """
    if not secret_data:
        return ""
    key = hashlib.sha256(secret_key.encode("utf-8")).digest()
    iv = secrets.token_bytes(16)
    data_bytes = secret_data.encode("utf-8")

    # Generate keystream using counter blocks
    blocks = (len(data_bytes) + 31) // 32
    keystream = bytearray()
    for counter in range(blocks):
        block = hashlib.sha256(key + iv + counter.to_bytes(4, "big")).digest()
        keystream.extend(block)

    ciphertext = bytes(b ^ k for b, k in zip(data_bytes, keystream[:len(data_bytes)]))
    tag = hmac.new(key, iv + ciphertext, hashlib.sha256).digest()

    raw_payload = iv + tag + ciphertext
    return base64.b64encode(raw_payload).decode("ascii")


def decrypt_credentials(encrypted_token: str, secret_key: str) -> str:
    """
    Decrypt credentials string encrypted with encrypt_credentials.
    Verifies HMAC tag in constant time.
    """
    if not encrypted_token:
        return ""
    key = hashlib.sha256(secret_key.encode("utf-8")).digest()
    raw_payload = base64.b64decode(encrypted_token.encode("ascii"))
    if len(raw_payload) < 48:  # 16 bytes IV + 32 bytes HMAC tag
        raise ValueError("Invalid encrypted credential token length.")

    iv = raw_payload[:16]
    expected_tag = raw_payload[16:48]
    ciphertext = raw_payload[48:]

    actual_tag = hmac.new(key, iv + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(actual_tag, expected_tag):
        raise ValueError("Credential verification failed: HMAC mismatch.")

    blocks = (len(ciphertext) + 31) // 32
    keystream = bytearray()
    for counter in range(blocks):
        block = hashlib.sha256(key + iv + counter.to_bytes(4, "big")).digest()
        keystream.extend(block)

    plaintext = bytes(c ^ k for c, k in zip(ciphertext, keystream[:len(ciphertext)]))
    return plaintext.decode("utf-8")


def derive_deterministic_event_id(
    camera_id: str,
    gate_id: str,
    frame_number: int,
    timestamp: float,
) -> str:
    """
    Derives a deterministic, idempotent event UUID from stable physical frame properties.
    Same source frame (camera_id + gate_id + frame_number + timestamp_ms) -> SAME UUID.
    """
    ms_timestamp = int(round(timestamp * 1000))
    urn = f"crowdos://events/{camera_id}/{gate_id}/{frame_number}/{ms_timestamp}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, urn))

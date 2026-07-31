"""Small authenticated encryption envelope for database-backed credentials.

The runtime deliberately keeps this module independent from provider SDKs.  It
uses a SHA-256/HMAC based stream envelope from the Python standard library so
the minimal local installation does not need a crypto wheel.  Deployments must
provide a high-entropy ``UAI_FORGE_CREDENTIAL_MASTER_KEY`` (or an equivalent
secret-manager injected value); the development fallback is only for local
tests and must not be used for production data.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from typing import Final


class SecretDecryptionError(ValueError):
    """Raised when a stored credential cannot be authenticated or decoded."""


_VERSION: Final[bytes] = b"uai-credential-v1"
_NONCE_BYTES: Final[int] = 16
_TAG_BYTES: Final[int] = 32


def _key(master_key: str) -> bytes:
    if not master_key:
        raise ValueError("credential master key must not be empty")
    return hashlib.sha256(master_key.encode("utf-8")).digest()


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    chunks = []
    counter = 0
    while sum(len(item) for item in chunks) < length:
        chunks.append(hmac.new(key, _VERSION + nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest())
        counter += 1
    return b"".join(chunks)[:length]


def _xor(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right))


def encrypt_secret(master_key: str, plaintext: str) -> str:
    key = _key(master_key)
    nonce = secrets.token_bytes(_NONCE_BYTES)
    raw = plaintext.encode("utf-8")
    ciphertext = _xor(raw, _keystream(key, nonce, len(raw)))
    tag = hmac.new(key, _VERSION + nonce + ciphertext, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(_VERSION + nonce + ciphertext + tag).decode("ascii")


def decrypt_secret(master_key: str, envelope: str) -> str:
    try:
        raw = base64.urlsafe_b64decode(envelope.encode("ascii"))
    except (ValueError, UnicodeError) as exc:
        raise SecretDecryptionError("invalid credential envelope") from exc
    if not raw.startswith(_VERSION):
        raise SecretDecryptionError("unsupported credential envelope")
    offset = len(_VERSION)
    if len(raw) < offset + _NONCE_BYTES + _TAG_BYTES:
        raise SecretDecryptionError("truncated credential envelope")
    nonce = raw[offset : offset + _NONCE_BYTES]
    ciphertext = raw[offset + _NONCE_BYTES : -_TAG_BYTES]
    tag = raw[-_TAG_BYTES:]
    key = _key(master_key)
    expected = hmac.new(key, _VERSION + nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected):
        raise SecretDecryptionError("credential authentication failed")
    try:
        return _xor(ciphertext, _keystream(key, nonce, len(ciphertext))).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SecretDecryptionError("credential payload is invalid") from exc


def mask_secret(value: str) -> str:
    """Return a stable, non-sensitive display hint for a credential."""

    if len(value) <= 8:
        return "••••"
    return f"{value[:3]}…{value[-4:]}"

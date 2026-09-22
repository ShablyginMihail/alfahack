from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_KEY_BYTES = 32
_NONCE_BYTES = 12


def decode_key(value: str | None) -> bytes:
    """Decode a base64 key into exactly 32 bytes, or generate a fresh one."""
    if value is None:
        return secrets.token_bytes(_KEY_BYTES)
    try:
        key = base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise ValueError("key must be base64-encoded") from exc
    if len(key) != _KEY_BYTES:
        raise ValueError(f"key must decode to {_KEY_BYTES} bytes")
    return key


class RecordCipher:
    """AES-256-GCM encryption with HMAC-SHA256 fingerprinting."""

    def __init__(self, encryption_key: bytes, hmac_key: bytes) -> None:
        if len(encryption_key) != _KEY_BYTES:
            raise ValueError(f"encryption_key must be {_KEY_BYTES} bytes")
        if len(hmac_key) != _KEY_BYTES:
            raise ValueError(f"hmac_key must be {_KEY_BYTES} bytes")
        self._aesgcm = AESGCM(encryption_key)
        self._hmac_key = hmac_key

    def encrypt(self, record_key: str, data: bytes) -> bytes:
        nonce = os.urandom(_NONCE_BYTES)
        ciphertext = self._aesgcm.encrypt(nonce, data, record_key.encode("utf-8"))
        return nonce + ciphertext

    def decrypt(self, record_key: str, blob: bytes) -> bytes:
        if len(blob) < _NONCE_BYTES:
            raise ValueError("ciphertext too short")
        nonce = blob[:_NONCE_BYTES]
        ciphertext = blob[_NONCE_BYTES:]
        try:
            return self._aesgcm.decrypt(nonce, ciphertext, record_key.encode("utf-8"))
        except InvalidTag as exc:
            raise ValueError("decryption failed") from exc

    def fingerprint(self, text: str) -> str:
        digest = hmac.new(self._hmac_key, text.encode("utf-8"), hashlib.sha256)
        return digest.hexdigest()

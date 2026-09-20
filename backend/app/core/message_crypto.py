"""Application-level encryption for private chat messages (AES-256-GCM).

What this protects: message text is stored in the database ONLY as
ciphertext. A leaked database dump, a backup, or anyone with read access to
Supabase sees unreadable blobs. What it does NOT do: it is not end-to-end
encryption — the API server holds the key and decrypts messages to serve them
to the two people in the conversation. (True E2EE would mean the server can
never read them, which also means no recovery when someone clears their
browser or changes phone, and no way for the school to act on abuse reports.)

Design:
  * A master key ring from MESSAGE_ENCRYPTION_KEYS; the highest version
    encrypts new messages, all versions decrypt (so keys can be rotated).
  * A separate subkey per conversation via HKDF-SHA256, so no two
    conversations share an encryption key.
  * A fresh random 96-bit nonce for every message.
  * The conversation id, message id and sender id are bound in as
    authenticated data: a database row copied into another conversation, or
    with a swapped sender, fails to decrypt instead of silently displaying.
"""

import base64
import logging
import os
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings

logger = logging.getLogger(__name__)


class DecryptionError(Exception):
    pass


@lru_cache(maxsize=1)
def _key_ring() -> dict[int, bytes]:
    ring: dict[int, bytes] = {}
    if settings.message_encryption_keys:
        for part in settings.message_encryption_keys.split(","):
            version, _, b64 = part.strip().partition(":")
            ring[int(version)] = base64.b64decode(b64)
    elif settings.environment != "production":
        # Development convenience only: derive a key from JWT_SECRET so local
        # dev works with zero setup. Production refuses to start without real keys.
        logger.warning("MESSAGE_ENCRYPTION_KEYS not set — using a development key derived from JWT_SECRET")
        ring[0] = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"ledgr-dev-message-key").derive(
            settings.jwt_secret.encode()
        )
    if not ring:
        raise RuntimeError("No message encryption key configured")
    return ring


def _subkey(master: bytes, conversation_id: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"ledgr-dm|" + conversation_id.encode()).derive(master)


def _aad(conversation_id: str, message_id: str, sender_id: str) -> bytes:
    return f"{conversation_id}|{message_id}|{sender_id}".encode()


def current_key_version() -> int:
    return max(_key_ring())


def encrypt_text(plaintext: str, conversation_id: str, message_id: str, sender_id: str) -> tuple[str, int]:
    """Returns (token, key_version). Token format: "<version>.<base64url(nonce+ciphertext)>"."""
    version = current_key_version()
    nonce = os.urandom(12)
    ct = AESGCM(_subkey(_key_ring()[version], conversation_id)).encrypt(
        nonce, plaintext.encode("utf-8"), _aad(conversation_id, message_id, sender_id)
    )
    return f"{version}." + base64.urlsafe_b64encode(nonce + ct).decode(), version


def decrypt_text(token: str, conversation_id: str, message_id: str, sender_id: str) -> str:
    try:
        version_s, _, payload = token.partition(".")
        master = _key_ring()[int(version_s)]
        raw = base64.urlsafe_b64decode(payload)
        nonce, ct = raw[:12], raw[12:]
        return AESGCM(_subkey(master, conversation_id)).decrypt(
            nonce, ct, _aad(conversation_id, message_id, sender_id)
        ).decode("utf-8")
    except (InvalidTag, KeyError, ValueError) as exc:
        raise DecryptionError("Message could not be decrypted") from exc

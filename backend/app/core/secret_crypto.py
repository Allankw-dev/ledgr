"""Encryption for secrets we must be able to use later (a school's M-Pesa key, secret and passkey).

Same AES-256-GCM and the same key ring as private messages (MESSAGE_ENCRYPTION_KEYS, so there is no extra
setting to forget in production, and rotating the ring rotates both), but a SEPARATE derivation label: a key
derived for a secret is never the key derived for a chat, so one domain can't be decrypted as the other.

`context` says exactly what the secret is ("mpesa|<school id>|consumer_key"). It selects the derived key AND is
bound in as authenticated data, so a ciphertext copied to another school or another field fails to decrypt
instead of quietly being used.

Losing the key ring means losing these secrets (they would have to be entered again), exactly as for messages.
"""

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.message_crypto import DecryptionError, _key_ring, current_key_version


def _subkey(master: bytes, context: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"ledgr-secret|" + context.encode()).derive(master)


def encrypt_secret(plaintext: str, context: str) -> str:
    """Token format: "<key version>.<base64url(nonce + ciphertext)>"."""
    version = current_key_version()
    nonce = os.urandom(12)
    ct = AESGCM(_subkey(_key_ring()[version], context)).encrypt(nonce, plaintext.encode("utf-8"), context.encode())
    return f"{version}." + base64.urlsafe_b64encode(nonce + ct).decode()


def decrypt_secret(token: str, context: str) -> str:
    try:
        version_s, _, payload = token.partition(".")
        raw = base64.urlsafe_b64decode(payload)
        return AESGCM(_subkey(_key_ring()[int(version_s)], context)).decrypt(raw[:12], raw[12:], context.encode()).decode("utf-8")
    except (InvalidTag, KeyError, ValueError) as exc:
        raise DecryptionError("Secret could not be decrypted") from exc

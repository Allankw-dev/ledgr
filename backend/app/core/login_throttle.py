"""Per-ACCOUNT brake on password guessing.

Why this exists: sign-in used to be limited only per IP address (10/minute). That is both too
tight and too weak. Too tight, because a whole school's parents often share one public IP
(school wifi, or a mobile carrier that puts thousands of phones behind one address), so at the
start of term the 11th parent in a minute was refused. Too weak, because a guesser who spreads
attempts over many IPs was never slowed down for any ONE account.

So the per-IP limit is now generous, and the real protection is here: after MAX_FAILURES wrong
passwords for the same email/phone within WINDOW_SECONDS, that account refuses further sign-in
attempts until the window passes. A correct password resets the counter. Password reset still
works while locked, so a genuine owner is never stuck.

Counters live in Redis when REDIS_URL is set (shared by every worker/instance), otherwise in this
process (each worker counts separately — weaker, fine for a single small instance). If Redis is
down this fails OPEN: a broken cache must never stop people signing in.
"""

import hashlib
import logging
import threading
import time

from app.core.cache import _redis_client
from app.core.phone import phone_key

logger = logging.getLogger(__name__)

MAX_FAILURES = 8
WINDOW_SECONDS = 15 * 60

_local: dict[str, tuple[int, float]] = {}  # key -> (failures, window_started_monotonic)
_lock = threading.Lock()


def _key(identifier: str) -> str:
    ident = (identifier or "").strip()
    normal = ident.lower() if "@" in ident else (phone_key(ident) or ident)
    return "login-fail:" + hashlib.sha256(normal.encode()).hexdigest()[:32]  # never store the raw email/phone


def is_locked(identifier: str) -> bool:
    key = _key(identifier)
    try:
        client = _redis_client()
        if client is not None:
            return int(client.get(key) or 0) >= MAX_FAILURES
    except Exception:  # noqa: BLE001
        logger.warning("login throttle: Redis unavailable, not enforcing the per-account limit")
        return False
    with _lock:
        failures, started = _local.get(key, (0, 0.0))
        if failures and time.monotonic() - started > WINDOW_SECONDS:
            _local.pop(key, None)
            return False
        return failures >= MAX_FAILURES


def record_failure(identifier: str) -> None:
    key = _key(identifier)
    try:
        client = _redis_client()
        if client is not None:
            if client.incr(key) == 1:
                client.expire(key, WINDOW_SECONDS)
            return
    except Exception:  # noqa: BLE001
        return
    with _lock:
        failures, started = _local.get(key, (0, 0.0))
        if not failures or time.monotonic() - started > WINDOW_SECONDS:
            failures, started = 0, time.monotonic()
        _local[key] = (failures + 1, started)
        if len(_local) > 50_000:  # a flood of made-up identifiers must not grow memory forever
            for k in [k for k, (_, s) in _local.items() if time.monotonic() - s > WINDOW_SECONDS]:
                _local.pop(k, None)


def clear(identifier: str) -> None:
    key = _key(identifier)
    try:
        client = _redis_client()
        if client is not None:
            client.delete(key)
            return
    except Exception:  # noqa: BLE001
        return
    with _lock:
        _local.pop(key, None)

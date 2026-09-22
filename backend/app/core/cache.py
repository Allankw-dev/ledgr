"""Small read-through cache with safe invalidation.

  * Backed by Redis when REDIS_URL is set (shared by every worker/instance, so
    an invalidation is seen everywhere immediately); otherwise an in-process
    dict with a TTL (per worker — an invalidation reaches the other workers
    only when their short TTL expires).
  * FAIL-OPEN: if Redis is down the loader just runs. A cache must never be
    the reason a request fails.
  * Invalidation by *namespace version*: every key embeds a per-(school,
    namespace) counter; bumping it orphans all old entries at once (they
    expire on their own TTL). No key scanning, no race between "delete" and
    a concurrent "set" of stale data.
  * Single-flight per process: when a hot key expires, one thread recomputes
    while the others wait, instead of N requests all hitting the database.

Only cache data that is (a) read far more often than written, (b) fine to be
up to TTL seconds stale — dashboards and setup lists, never a balance that a
payment screen needs to be exact.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable

from app.core.config import settings

logger = logging.getLogger(__name__)

try:  # redis is optional at import time
    import redis as _redis
except Exception:  # noqa: BLE001
    _redis = None

_client = None
_client_lock = threading.Lock()


def _redis_client():
    global _client
    if not settings.redis_url or _redis is None:
        return None
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = _redis.Redis.from_url(
                    settings.redis_url, socket_timeout=0.25, socket_connect_timeout=0.25, decode_responses=True
                )
    return _client


# in-process fallback: key -> (expires_at_monotonic, json_string)
_local: dict[str, tuple[float, str]] = {}
_local_versions: dict[str, int] = {}
_local_lock = threading.Lock()
_flight_locks: dict[str, threading.Lock] = {}


def _version(school_id: str, namespace: str) -> int:
    vkey = f"ledgr:v:{school_id}:{namespace}"
    r = _redis_client()
    if r is not None:
        try:
            return int(r.get(vkey) or 0)
        except Exception:  # noqa: BLE001
            logger.warning("cache: redis unavailable reading version", exc_info=False)
    return _local_versions.get(vkey, 0)


def bump(school_id: str, namespace: str) -> None:
    """Invalidate everything cached under (school, namespace). Call AFTER the
    transaction that changed the data has committed."""
    vkey = f"ledgr:v:{school_id}:{namespace}"
    with _local_lock:
        _local_versions[vkey] = _local_versions.get(vkey, 0) + 1
    r = _redis_client()
    if r is not None:
        try:
            r.incr(vkey)
        except Exception:  # noqa: BLE001
            logger.warning("cache: redis unavailable during invalidation", exc_info=False)


def _get(key: str) -> str | None:
    r = _redis_client()
    if r is not None:
        try:
            return r.get(key)
        except Exception:  # noqa: BLE001
            return None
    hit = _local.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    return None


def _set(key: str, value: str, ttl: int) -> None:
    r = _redis_client()
    if r is not None:
        try:
            r.set(key, value, ex=ttl)
            return
        except Exception:  # noqa: BLE001
            return
    with _local_lock:
        if len(_local) > 5000:  # bound memory
            _local.clear()
        _local[key] = (time.monotonic() + ttl, value)


def cached(
    school_id: str,
    namespace: str,
    name: str,
    loader: Callable[[], Any],
    ttl: int | None = None,
) -> Any:
    """Return the cached JSON-able value, or run `loader()` and cache it.
    `loader` must return something json.dumps can handle (use model_dump(mode="json"))."""
    ttl = ttl or settings.cache_default_ttl_seconds
    key = f"ledgr:c:{school_id}:{namespace}:{_version(school_id, namespace)}:{name}"

    raw = _get(key)
    if raw is not None:
        return json.loads(raw)

    with _local_lock:
        flight = _flight_locks.setdefault(key, threading.Lock())
    with flight:
        raw = _get(key)  # someone else may have filled it while we waited
        if raw is not None:
            return json.loads(raw)
        value = loader()
        _set(key, json.dumps(value, default=str), ttl)
    with _local_lock:
        _flight_locks.pop(key, None)
    return value

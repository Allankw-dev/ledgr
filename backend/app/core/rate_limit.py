import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

logger = logging.getLogger(__name__)

# Shared across main.py (registers the exception handler) and any router
# that needs to rate-limit specific endpoints via @limiter.limit(...).
# Keeping this in its own module avoids main.py <-> routers circular imports.
#
# With REDIS_URL set, counters live in Redis so limits hold across every
# worker/instance and survive restarts. Without it, counters are per-process
# (fine for local dev, but with N workers each user effectively gets N x the
# limit). If Redis goes down at runtime, in_memory_fallback_enabled keeps
# rate limiting alive per-process instead of turning every request into a 500.
#
# key_func reads request.client.host, which is the *proxy's* address unless
# uvicorn/gunicorn is started with proxy headers enabled and the proxy is
# trusted (see run.py / gunicorn_conf.py). Without that, everyone behind a
# load balancer shares one rate-limit bucket.
if settings.redis_url:
    logger.info("Rate limiting: using Redis storage")
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri=settings.redis_url,
        in_memory_fallback_enabled=True,
    )
else:
    limiter = Limiter(key_func=get_remote_address)

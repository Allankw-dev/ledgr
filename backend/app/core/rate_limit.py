import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.security import decode_access_token

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
def user_or_ip_key(request) -> str:
    """Who a request counts against.

    A signed-in request counts against ITS USER, not its IP address. Per-IP was wrong for the
    people this app serves: a school's wifi, or a mobile carrier that puts thousands of phones
    behind one public address, makes dozens of different parents look like one client — so
    ordinary background polling (the unread badge, chat) used up a shared allowance and real
    users started getting "too many requests". Requests with no valid token (sign-in, sign-up,
    password reset) still count per IP, which is the right key before we know who someone is.

    Only a token whose signature checks out is trusted for this; a forged or expired one just
    falls back to the IP bucket, so it can't be used to dodge a limit or fill someone else's."""
    auth = request.headers.get("authorization", "")
    if auth[:7].lower() == "bearer ":
        try:
            payload = decode_access_token(auth[7:].strip())
            if payload.get("sub") and payload.get("role"):  # an access token, not a 2FA/reset one
                return f"user:{payload['sub']}"
        except Exception:  # noqa: BLE001
            pass
    return get_remote_address(request)


if settings.redis_url:
    logger.info("Rate limiting: using Redis storage")
    limiter = Limiter(
        key_func=user_or_ip_key,
        storage_uri=settings.redis_url,
        in_memory_fallback_enabled=True,
    )
else:
    limiter = Limiter(key_func=user_or_ip_key)

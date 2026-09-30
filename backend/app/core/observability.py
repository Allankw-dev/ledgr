"""Logging, request tracing and error reporting.

- One log line per request (method, path, status, ms) tagged with a request id
  that is also returned to the client as X-Request-ID, so a user's "it failed"
  can be traced to exact log lines and the matching Sentry event.
- Slow (>SLOW_REQUEST_MS) and 5xx requests are logged at WARNING.
- Only the URL *path* is logged, never the query string: the M-Pesa callback
  carries its secret there (?token=...).
- Sentry is optional (SENTRY_DSN) and drops expected 4xx noise.
"""
import contextvars
import logging
import os
import time
import uuid

from app.core.config import settings

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_request_logger = logging.getLogger("ledgr.request")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging() -> None:
    """Make app logs (INFO+) visible in Render/host logs, with request ids."""
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
    for handler in root.handlers:
        handler.setFormatter(fmt)
        handler.addFilter(_RequestIdFilter())
    # Chatty libraries at WARNING so the useful lines stand out.
    for noisy in ("httpx", "httpcore", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def init_sentry() -> None:
    if not settings.sentry_dsn:
        return
    import sentry_sdk
    from starlette.exceptions import HTTPException

    def before_send(event, hint):
        exc = (hint.get("exc_info") or (None, None, None))[1]
        # 401/403/404/422/429 are normal client behaviour, not incidents.
        if isinstance(exc, HTTPException) and exc.status_code < 500:
            return None
        return event

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=os.getenv("RENDER_GIT_COMMIT") or None,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,  # financial app: never ship user data to third parties
        before_send=before_send,
    )


class RequestLogMiddleware:
    """Pure ASGI (no BaseHTTPMiddleware overhead)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope["path"]
        headers = dict(scope.get("headers") or [])
        rid = (headers.get(b"x-request-id") or b"").decode()[:64] or uuid.uuid4().hex[:12]
        token = request_id_var.set(rid)
        try:
            import sentry_sdk

            sentry_sdk.set_tag("request_id", rid)
        except Exception:  # noqa: BLE001
            pass

        status = {"code": 500}  # stays 500 if the app raises before responding
        start = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                message["headers"] = list(message.get("headers", [])) + [(b"x-request-id", rid.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            ms = (time.perf_counter() - start) * 1000
            if not path.startswith("/health"):  # uptime pings every few minutes — skip
                line = "%s %s %s %.0fms" % (scope["method"], path, status["code"], ms)
                if status["code"] >= 500 or ms >= settings.slow_request_ms:
                    _request_logger.warning(line)
                else:
                    _request_logger.info(line)
            request_id_var.reset(token)

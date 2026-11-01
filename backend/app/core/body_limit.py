"""Refuses oversized request bodies before the app reads them (pure ASGI, so it costs nothing on small requests).

Without this, nothing stopped a single request from carrying a 200 MB "student name" that the server would read
into memory and try to store. Rate limits cap how OFTEN someone can ask; this caps how BIG each ask can be.

  * ordinary JSON requests: 1 MiB (the largest real payload in the app is a few kilobytes);
  * file uploads (paths ending in /upload): the configured MAX_UPLOAD_MB plus 1 MiB for the form framing.

A body that declares its size (Content-Length) is refused immediately. One that doesn't (chunked transfer) is
counted as it streams and cut off the moment it passes the limit. GET/HEAD/OPTIONS carry no body and are skipped.
"""

import json

from app.core.config import settings

JSON_LIMIT = 1024 * 1024
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class _TooLarge(BaseException):
    """Deliberately a BaseException: FastAPI wraps body reading in `except Exception` and would turn an
    ordinary exception into a generic 400 "error parsing the body". This has to reach us untouched so the
    client gets the honest 413."""


def _limit_for(path: str) -> int:
    if path.endswith("/upload"):
        return (settings.max_upload_mb + 1) * 1024 * 1024
    return JSON_LIMIT


async def _send_413(send, limit: int) -> None:
    body = json.dumps({"detail": f"Request is too large (limit {limit // 1024} KB)."}).encode()
    await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})


class BodySizeLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in _SAFE_METHODS:
            return await self.app(scope, receive, send)

        limit = _limit_for(scope["path"])
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None:
            try:
                too_big = int(declared) > limit
            except ValueError:
                too_big = True  # a Content-Length that isn't a number is not a request worth reading
            if too_big:
                return await _send_413(send, limit)

        seen = 0
        started = False

        async def counting_receive():
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    raise _TooLarge()
            return message

        async def tracking_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _TooLarge:
            if not started:
                await _send_413(send, limit)

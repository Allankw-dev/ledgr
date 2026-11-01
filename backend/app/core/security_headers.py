"""Adds baseline security headers to every response (pure ASGI — no
BaseHTTPMiddleware overhead)."""

from app.core.config import settings

_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
]
if settings.is_production_like:
    # Only send HSTS outside a developer machine, where the API is served over HTTPS.
    _HEADERS.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {k.lower() for k, _ in headers}
                extra = [h for h in _HEADERS if h[0] not in existing]
                # JSON from this API is personal financial data. Tell browsers and proxies not to keep a copy
                # (a shared school computer's cache would otherwise hold the last parent's fee balances).
                # Only JSON, and only when the route didn't choose its own policy: file downloads keep theirs.
                is_json = any(k.lower() == b"content-type" and v.lower().startswith(b"application/json") for k, v in headers)
                if is_json and b"cache-control" not in existing:
                    extra.append((b"cache-control", b"no-store"))
                message["headers"] = headers + extra
            await send(message)

        await self.app(scope, receive, send_with_headers)

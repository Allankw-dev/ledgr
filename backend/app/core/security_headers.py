"""Adds baseline security headers to every response (pure ASGI — no
BaseHTTPMiddleware overhead)."""

from app.core.config import settings

_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
]
if settings.environment == "production":
    # Only send HSTS in production, where the API is served over HTTPS.
    _HEADERS.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                existing = {k.lower() for k, _ in message.get("headers", [])}
                message["headers"] = list(message.get("headers", [])) + [h for h in _HEADERS if h[0] not in existing]
            await send(message)

        await self.app(scope, receive, send_with_headers)

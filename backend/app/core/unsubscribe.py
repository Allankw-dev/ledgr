"""Unsubscribe links for optional email (fee reminders, overdue notices, school announcements).

The token is a signed, long-lived JWT naming one user and carrying purpose="unsubscribe". It can do exactly one
thing: switch that person's optional email off (or back on). decode_access_token refuses any token with a
`purpose` claim, so it can never be used as a login token.
"""

from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
from app.core.security import JWTError, decode_token

PURPOSE = "unsubscribe"
_LIFETIME = timedelta(days=730)  # an old email's link should still work; it can only switch mail off


def create_unsubscribe_token(user_id: str) -> str:
    payload = {"sub": user_id, "purpose": PURPOSE, "exp": datetime.now(timezone.utc) + _LIFETIME}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_unsubscribe_token(token: str) -> str:
    """Returns the user id, or raises ValueError."""
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise ValueError("Invalid or expired link") from exc
    if payload.get("purpose") != PURPOSE or not payload.get("sub"):
        raise ValueError("Invalid or expired link")
    return payload["sub"]


def unsubscribe_page_url(user_id: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/unsubscribe?token={create_unsubscribe_token(user_id)}"


def one_click_url(user_id: str) -> str | None:
    """The API address mail apps POST to for one-tap unsubscribe (RFC 8058). None when the API's public address
    isn't configured, in which case only the footer link is used."""
    if not settings.api_public_url:
        return None
    return f"{settings.api_public_url.rstrip('/')}/api/privacy/unsubscribe/one-click?token={create_unsubscribe_token(user_id)}"

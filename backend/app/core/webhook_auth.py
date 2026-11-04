"""Authentication for Safaricom's M-Pesa webhooks.

Safaricom does not sign its callbacks, so the URL itself has to be the
secret: register callback URLs that carry a long random ?token=..., and only
requests that present it are accepted. An optional IP allowlist adds a
second layer. Without this, anyone who can reach /api/payments/... can POST
a fake "payment received" and get an invoice marked paid.

Two kinds of token are accepted:
  * the server-wide MPESA_CALLBACK_SECRET (the original single-paybill setup), and
  * a SCHOOL token (see services/mpesa_accounts.py) for a school with its own paybill.
The result says which was used, so a handler can refuse to let a school's token affect another school's payments.
"""

import hmac
import logging
from dataclasses import dataclass

from fastapi import HTTPException, Request

from app.core.config import settings
from app.services.mpesa_accounts import verify_school_webhook_token

logger = logging.getLogger("ledgr.mpesa")


@dataclass(frozen=True)
class WebhookAuth:
    school_id: str | None  # the school whose own token was presented; None = the server-wide token


def _check_ip(client_ip: str | None) -> None:
    allowed = [ip.strip() for ip in (settings.mpesa_allowed_ips or "").split(",") if ip.strip()]
    if allowed and client_ip not in allowed:
        logger.warning("Rejected M-Pesa webhook from non-allowlisted IP %s", client_ip)
        raise HTTPException(403, "Forbidden")


def verify_mpesa_webhook(request: Request) -> WebhookAuth:
    client_ip = request.client.host if request.client else None
    supplied = request.query_params.get("token", "")

    if supplied.count(".") == 2:
        school_id = verify_school_webhook_token(supplied)
        if school_id:
            _check_ip(client_ip)
            return WebhookAuth(school_id=school_id)
        # Not a valid school token: fall through, it may be a server-wide secret that happens to contain dots.

    secret = settings.mpesa_callback_secret
    if not secret:
        if settings.environment == "production":
            # Settings validation already refuses to boot like this; belt and braces.
            raise HTTPException(503, "M-Pesa webhooks are not configured")
        logger.warning("MPESA_CALLBACK_SECRET is not set — accepting unauthenticated M-Pesa webhook (non-production only)")
        return WebhookAuth(school_id=None)

    if not hmac.compare_digest(supplied.encode(), secret.encode()):
        logger.warning("Rejected M-Pesa webhook with missing/invalid token from %s", client_ip)
        raise HTTPException(403, "Forbidden")

    _check_ip(client_ip)
    return WebhookAuth(school_id=None)

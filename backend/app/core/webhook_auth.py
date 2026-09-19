"""Authentication for Safaricom's M-Pesa webhooks.

Safaricom does not sign its callbacks, so the URL itself has to be the
secret: register callback URLs that carry a long random ?token=..., and only
requests that present it are accepted. An optional IP allowlist adds a
second layer. Without this, anyone who can reach /api/payments/... can POST
a fake "payment received" and get an invoice marked paid.
"""

import hmac
import logging

from fastapi import HTTPException, Request

from app.core.config import settings

logger = logging.getLogger("ledgr.mpesa")


def verify_mpesa_webhook(request: Request) -> None:
    client_ip = request.client.host if request.client else None
    secret = settings.mpesa_callback_secret

    if not secret:
        if settings.environment == "production":
            # Settings validation already refuses to boot like this; belt and braces.
            raise HTTPException(503, "M-Pesa webhooks are not configured")
        logger.warning("MPESA_CALLBACK_SECRET is not set — accepting unauthenticated M-Pesa webhook (non-production only)")
        return

    supplied = request.query_params.get("token", "")
    if not hmac.compare_digest(supplied.encode(), secret.encode()):
        logger.warning("Rejected M-Pesa webhook with missing/invalid token from %s", client_ip)
        raise HTTPException(403, "Forbidden")

    allowed = [ip.strip() for ip in (settings.mpesa_allowed_ips or "").split(",") if ip.strip()]
    if allowed and client_ip not in allowed:
        logger.warning("Rejected M-Pesa webhook from non-allowlisted IP %s", client_ip)
        raise HTTPException(403, "Forbidden")

"""
One-time (per-environment) script: tells Safaricom which URLs to call
whenever someone pays your paybill directly (C2B) — as opposed to STK push,
which needs no registration since Daraja already knows the callback URL
from each /stk-push request.

Run this ONCE per environment (once for sandbox while testing, once again
for production after Safaricom approves your paybill) — not on every
deploy. Re-running it is harmless (Safaricom just overwrites the previous
registration), but it isn't part of the app's normal startup.

Usage:
    cd backend
    python -m scripts.register_c2b_urls

Requires in your .env (see .env.example):
    MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET, MPESA_SHORTCODE
    MPESA_C2B_VALIDATION_URL, MPESA_C2B_CONFIRMATION_URL
"""

import asyncio
import sys

import httpx

from app.core.config import settings
from app.services.mpesa_service import get_access_token, DARAJA_BASE_URL, MpesaConfigError


async def register() -> None:
    missing = [
        name
        for name, value in [
            ("MPESA_SHORTCODE", settings.mpesa_shortcode),
            ("MPESA_C2B_VALIDATION_URL", settings.mpesa_c2b_validation_url),
            ("MPESA_C2B_CONFIRMATION_URL", settings.mpesa_c2b_confirmation_url),
        ]
        if not value
    ]
    if missing:
        print(f"Missing required settings: {', '.join(missing)}", file=sys.stderr)
        print("Set these in backend/.env before running this script.", file=sys.stderr)
        sys.exit(1)

    if not settings.mpesa_c2b_validation_url.startswith("https://") or not settings.mpesa_c2b_confirmation_url.startswith("https://"):
        print("Both C2B URLs must be public HTTPS URLs — Safaricom will not call http:// or localhost URLs.", file=sys.stderr)
        sys.exit(1)

    try:
        token = await get_access_token()
    except MpesaConfigError as exc:
        print(f"M-Pesa is not fully configured: {exc}", file=sys.stderr)
        sys.exit(1)

    payload = {
        "ShortCode": settings.mpesa_shortcode,
        "ResponseType": "Completed",  # what Safaricom does if OUR server times out on /validation — see note below
        "ConfirmationURL": settings.mpesa_c2b_confirmation_url,
        "ValidationURL": settings.mpesa_c2b_validation_url,
    }

    print(f"Registering C2B URLs against {DARAJA_BASE_URL} for shortcode {settings.mpesa_shortcode}:")
    print(f"  ConfirmationURL = {settings.mpesa_c2b_confirmation_url}")
    print(f"  ValidationURL   = {settings.mpesa_c2b_validation_url}")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DARAJA_BASE_URL}/mpesa/c2b/v2/registerurl",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )

    if resp.status_code >= 400:
        print(f"Registration failed ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)

    print("Registration succeeded:")
    print(resp.json())
    print(
        "\nNote: ResponseType=Completed means if Safaricom can't reach your "
        "/c2b/validation endpoint (server down, slow), it auto-accepts the "
        "payment rather than bouncing it — matches the app's own validation "
        "handler, which always accepts too (see the docstring on "
        "mpesa_c2b_validation in app/routers/mpesa.py)."
    )


if __name__ == "__main__":
    asyncio.run(register())

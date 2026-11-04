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

from app.core.config import settings
from app.services.mpesa_service import MpesaConfigError, global_credentials, register_c2b_urls


async def register() -> None:
    missing = [
        name
        for name, value in [
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
        creds = global_credentials()
    except MpesaConfigError as exc:
        print(f"M-Pesa is not fully configured: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Registering C2B URLs against {creds.base_url} for shortcode {creds.shortcode}:")
    print(f"  ConfirmationURL = {settings.mpesa_c2b_confirmation_url}")
    print(f"  ValidationURL   = {settings.mpesa_c2b_validation_url}")

    try:
        result = await register_c2b_urls(creds, settings.mpesa_c2b_validation_url, settings.mpesa_c2b_confirmation_url)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    print("Registration succeeded:")
    print(result)
    print(
        "\nNote: ResponseType=Completed means if Safaricom can't reach your "
        "/c2b/validation endpoint (server down, slow), it auto-accepts the "
        "payment rather than bouncing it — matches the app's own validation "
        "handler, which always accepts too (see the docstring on "
        "c2b_validation in app/routers/c2b.py).\n"
        "A school with its OWN paybill is registered from the platform screen (Schools and billing > Payments), "
        "not with this script."
    )


if __name__ == "__main__":
    asyncio.run(register())

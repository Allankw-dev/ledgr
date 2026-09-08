import base64
from datetime import datetime

import httpx

from app.core.config import settings

# Daraja base URL — defaults to the real sandbox, but overridable via
# MPESA_BASE_URL. This is what lets you point the whole M-Pesa integration
# at a local emulator (e.g. Pesa Playground) for testing, without touching
# any code — just set MPESA_BASE_URL=http://localhost:8001 in .env, then
# unset it (or set it to https://api.safaricom.co.ke) for production.
DARAJA_BASE_URL = settings.mpesa_base_url or "https://sandbox.safaricom.co.ke"


class MpesaConfigError(Exception):
    """Raised when M-Pesa credentials aren't configured — lets callers give
    a clear message instead of a confusing downstream HTTP failure."""


def _require_config() -> None:
    missing = [
        name
        for name, value in [
            ("MPESA_CONSUMER_KEY", settings.mpesa_consumer_key),
            ("MPESA_CONSUMER_SECRET", settings.mpesa_consumer_secret),
            ("MPESA_SHORTCODE", settings.mpesa_shortcode),
            ("MPESA_PASSKEY", settings.mpesa_passkey),
        ]
        if not value
    ]
    if missing:
        raise MpesaConfigError(f"M-Pesa is not configured — missing: {', '.join(missing)}")


async def get_access_token() -> str:
    """OAuth token from Daraja, required on every subsequent API call.
    Valid for 1 hour — callers should fetch a fresh one per request rather
    than caching across a long-running process, since the cost of one extra
    HTTP call is negligible compared to the bugs a stale-token cache invites."""
    _require_config()

    credentials = f"{settings.mpesa_consumer_key}:{settings.mpesa_consumer_secret}"
    encoded = base64.b64encode(credentials.encode()).decode()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DARAJA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials",
            headers={"Authorization": f"Basic {encoded}"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


def _generate_password_and_timestamp() -> tuple[str, str]:
    """Daraja requires shortcode+passkey+timestamp, base64-encoded, as the
    STK push 'Password' field — this is the exact recipe from Safaricom's docs."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    raw = f"{settings.mpesa_shortcode}{settings.mpesa_passkey}{timestamp}"
    password = base64.b64encode(raw.encode()).decode()
    return password, timestamp


async def initiate_stk_push(
    phone_number: str,
    amount: int,
    account_reference: str,
    transaction_desc: str,
    callback_url: str,
) -> dict:
    """
    Triggers the M-Pesa STK push — the parent's phone gets a prompt asking
    them to enter their PIN. Returns Daraja's immediate acknowledgement
    (CheckoutRequestID etc.), NOT the payment result — that arrives later,
    asynchronously, at callback_url once the parent responds on their phone.

    phone_number must be in the format 2547XXXXXXXX (no leading +, no
    leading 0) — Daraja rejects other formats.
    """
    _require_config()

    token = await get_access_token()
    password, timestamp = _generate_password_and_timestamp()

    payload = {
        "BusinessShortCode": settings.mpesa_shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": settings.mpesa_shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": callback_url,
        "AccountReference": account_reference[:12],  # Daraja truncates/rejects longer values
        "TransactionDesc": transaction_desc[:13],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DARAJA_BASE_URL}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if resp.status_code >= 400:
            # Safaricom's error responses contain a genuinely useful message
            # (e.g. "Invalid PhoneNumber", "Bad Request - Invalid Shortcode")
            # in the body — httpx's default raise_for_status() discards it,
            # which makes real failures here nearly undiagnosable. Surface it.
            raise RuntimeError(f"Daraja STK push failed ({resp.status_code}): {resp.text}")
        return resp.json()


def normalize_phone_number(phone: str) -> str:
    """
    Accepts common Kenyan formats a parent might type — 0712345678,
    +254712345678, 254712345678 — and returns the one Daraja requires:
    254712345678.
    """
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("0"):
        return "254" + digits[1:]
    if digits.startswith("254"):
        return digits
    if digits.startswith("7") or digits.startswith("1"):
        return "254" + digits
    return digits

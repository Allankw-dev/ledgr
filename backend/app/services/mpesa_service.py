import base64
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from app.core.config import settings

# Daraja base URLs. For the SERVER-WIDE settings, UNSET MEANS SAFARICOM'S SANDBOX (the test system: no real phone is
# ever prompted and no real money moves). For REAL payments you MUST set MPESA_BASE_URL=https://api.safaricom.co.ke
# explicitly. (An earlier version of this comment said to "unset it for production", which does the opposite.)
# MPESA_BASE_URL can also point the whole integration at a local emulator (e.g. Pesa Playground) for testing, without
# touching any code: MPESA_BASE_URL=http://localhost:8001 in .env.
# A school's OWN account does not depend on that guesswork: it states SANDBOX or PRODUCTION explicitly.
SANDBOX_URL = "https://sandbox.safaricom.co.ke"
PRODUCTION_URL = "https://api.safaricom.co.ke"
DARAJA_BASE_URL = settings.mpesa_base_url or SANDBOX_URL


class MpesaOutcomeUnknown(Exception):
    """The STK push request left our server but no answer came back (timeout, dropped
    connection), so Safaricom may well have prompted the phone. Callers must not assume
    either way — see routers/mpesa.py."""


class MpesaConfigError(Exception):
    """Raised when M-Pesa credentials aren't configured — lets callers give
    a clear message instead of a confusing downstream HTTP failure."""


@dataclass(frozen=True)
class MpesaCredentials:
    """Everything needed to talk to Daraja AS ONE PAYBILL. Passed explicitly into every call, so there is no
    ambient "the" paybill that one school's request could pick up by accident.

    The secrets are excluded from repr(), so they can never leak through a log line or a traceback."""

    shortcode: str
    base_url: str
    consumer_key: str = field(repr=False)
    consumer_secret: str = field(repr=False)
    passkey: str = field(repr=False)
    source: str = "global"  # "global" (server settings) or "school": for logs only


def global_credentials() -> MpesaCredentials:
    """The server-wide MPESA_* settings (the original single-paybill setup)."""
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
    return MpesaCredentials(
        shortcode=str(settings.mpesa_shortcode),
        base_url=DARAJA_BASE_URL,
        consumer_key=settings.mpesa_consumer_key,
        consumer_secret=settings.mpesa_consumer_secret,
        passkey=settings.mpesa_passkey,
        source="global",
    )


def base_url_for_environment(environment: str) -> str:
    if environment == "PRODUCTION":
        return PRODUCTION_URL
    return settings.mpesa_base_url or SANDBOX_URL


async def get_access_token(creds: MpesaCredentials) -> str:
    """OAuth token from Daraja, required on every subsequent API call.
    Valid for 1 hour — callers should fetch a fresh one per request rather
    than caching across a long-running process, since the cost of one extra
    HTTP call is negligible compared to the bugs a stale-token cache invites
    (and with several paybills, a cache is one more place to mix them up)."""
    encoded = base64.b64encode(f"{creds.consumer_key}:{creds.consumer_secret}".encode()).decode()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{creds.base_url}/oauth/v1/generate?grant_type=client_credentials",
            headers={"Authorization": f"Basic {encoded}"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


def _generate_password_and_timestamp(creds: MpesaCredentials) -> tuple[str, str]:
    """Daraja requires shortcode+passkey+timestamp, base64-encoded, as the
    STK push 'Password' field — this is the exact recipe from Safaricom's docs."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    raw = f"{creds.shortcode}{creds.passkey}{timestamp}"
    password = base64.b64encode(raw.encode()).decode()
    return password, timestamp


async def initiate_stk_push(
    creds: MpesaCredentials,
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
    token = await get_access_token(creds)
    password, timestamp = _generate_password_and_timestamp(creds)

    payload = {
        "BusinessShortCode": creds.shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": creds.shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": callback_url,
        "AccountReference": account_reference[:12],  # Daraja truncates/rejects longer values
        "TransactionDesc": transaction_desc[:13],
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{creds.base_url}/mpesa/stkpush/v1/processrequest",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise  # never connected, so nothing can have been sent
        except httpx.TransportError as exc:
            # Connected, then the answer was lost (read timeout, reset). The prompt may be out.
            raise MpesaOutcomeUnknown(str(exc) or exc.__class__.__name__) from exc
        if resp.status_code >= 400:
            # Safaricom's error responses contain a genuinely useful message
            # (e.g. "Invalid PhoneNumber", "Bad Request - Invalid Shortcode")
            # in the body — httpx's default raise_for_status() discards it,
            # which makes real failures here nearly undiagnosable. Surface it.
            raise RuntimeError(f"Daraja STK push failed ({resp.status_code}): {resp.text}")
        return resp.json()


async def register_c2b_urls(creds: MpesaCredentials, validation_url: str, confirmation_url: str) -> dict:
    """Tells Safaricom which URLs to call when someone pays this paybill directly (C2B). Re-running is harmless:
    Safaricom just overwrites the previous registration. Shared by scripts/register_c2b_urls.py and the
    platform screen, so there is one implementation."""
    token = await get_access_token(creds)
    payload = {
        "ShortCode": creds.shortcode,
        "ResponseType": "Completed",  # what Safaricom does if OUR server times out on /validation
        "ConfirmationURL": confirmation_url,
        "ValidationURL": validation_url,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{creds.base_url}/mpesa/c2b/v2/registerurl",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"Daraja C2B registration failed ({resp.status_code}): {resp.text}")
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

"""Which M-Pesa paybill does each school use, and how do we recognise its payments?

A school's `mpesa_mode` decides:

  OFF     online M-Pesa is not available. The default for every new school, so a school that has not been set up
          can never send its parents' money to someone else's paybill.
  GLOBAL  the server-wide MPESA_* settings: the original single-paybill setup, kept for the school that already
          uses it.
  OWN     the school's own paybill, saved (encrypted) in `school_mpesa_accounts` by the platform operator.

Three jobs live here:

  1. `channel_for_school`: the credentials and callback address to use for a school's STK push.
  2. Webhook tokens. Safaricom doesn't sign anything, so the address is the secret. A school's address carries a
     token derived from the server's webhook secret and that school's id, so it identifies WHICH school may be
     affected: a school's token can never touch another school's payments.
  3. `route_c2b`: a paybill payment arrives with the shortcode it was paid to. That shortcode says which school(s)
     it can belong to, and the payment is only ever matched against THOSE schools' students.

The credentials table is owner-only (see the migration), so every read here uses its own system session.
"""

import hashlib
import hmac
import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SystemSessionLocal
from app.core.secret_crypto import decrypt_secret, encrypt_secret
from app.models.mpesa_account import SchoolMpesaAccount
from app.models.school import School
from app.services.mpesa_service import MpesaConfigError, MpesaCredentials, base_url_for_environment, global_credentials

logger = logging.getLogger("ledgr.mpesa")

MODES = ("OFF", "GLOBAL", "OWN")
ENVIRONMENTS = ("SANDBOX", "PRODUCTION")

STK_CALLBACK_PATH = "/api/payments/mpesa/callback"
C2B_VALIDATION_PATH = "/api/payments/c2b/validation"
C2B_CONFIRMATION_PATH = "/api/payments/c2b/confirmation"


class MpesaNotAvailable(Exception):
    """Online M-Pesa isn't switched on for this school. `user_message` is safe to show a parent."""

    user_message = (
        "Online M-Pesa payments aren't switched on for this school yet. "
        "Please pay using the school's paybill or contact the school office."
    )


class TokenScopeMismatch(Exception):
    """A webhook token for one school was presented for something that belongs to another."""


# --------------------------------------------------------------------------------------------------
# Secrets: what is stored, and under what context it is bound
# --------------------------------------------------------------------------------------------------


def secret_context(school_id: str, field_name: str) -> str:
    return f"mpesa|{school_id}|{field_name}"


def encrypt_account_secret(school_id: str, field_name: str, value: str) -> str:
    return encrypt_secret(value, secret_context(school_id, field_name))


def credentials_from_account(account: SchoolMpesaAccount) -> MpesaCredentials:
    sid = account.school_id
    return MpesaCredentials(
        shortcode=account.shortcode,
        base_url=base_url_for_environment(account.environment),
        consumer_key=decrypt_secret(account.consumer_key_enc, secret_context(sid, "consumer_key")),
        consumer_secret=decrypt_secret(account.consumer_secret_enc, secret_context(sid, "consumer_secret")),
        passkey=decrypt_secret(account.passkey_enc, secret_context(sid, "passkey")),
        source="school",
    )


# --------------------------------------------------------------------------------------------------
# Webhook tokens
# --------------------------------------------------------------------------------------------------


def _webhook_master() -> bytes:
    # The same secret production already requires for the server-wide webhooks. (A development machine without one
    # falls back to JWT_SECRET so tokens still work there.)
    return (settings.mpesa_callback_secret or settings.jwt_secret).encode()


def _mac(school_id: str, version: int) -> str:
    # Hex, so the token can never contain the word "mpesa", which Daraja refuses in C2B addresses.
    return hmac.new(_webhook_master(), f"ledgr-mpesa-webhook|{school_id}|{version}".encode(), hashlib.sha256).hexdigest()


def school_webhook_token(school_id: str, version: int) -> str:
    return f"{school_id}.{version}.{_mac(school_id, version)}"


def verify_school_webhook_token(token: str) -> str | None:
    """Returns the school id the token was issued for, or None if it isn't a valid, current school token."""
    parts = (token or "").split(".")
    if len(parts) != 3:
        return None
    school_id, version_s, supplied = parts
    try:
        version = int(version_s)
    except ValueError:
        return None
    if not hmac.compare_digest(supplied.encode(), _mac(school_id, version).encode()):
        return None
    # A rotated token (version bumped) or a school that no longer has an account stops working at once.
    with SystemSessionLocal() as db:
        current = db.execute(
            select(SchoolMpesaAccount.callback_token_version).where(SchoolMpesaAccount.school_id == school_id)
        ).scalar_one_or_none()
    if current is None or current != version:
        return None
    return school_id


# --------------------------------------------------------------------------------------------------
# Public addresses given to Safaricom
# --------------------------------------------------------------------------------------------------


def public_origin() -> str | None:
    """Scheme + host of this API, taken from the addresses that are already configured, so no new setting is needed."""
    for candidate in (settings.mpesa_callback_url, settings.mpesa_c2b_confirmation_url, settings.mpesa_c2b_validation_url):
        if candidate:
            parts = urlsplit(candidate)
            if parts.scheme and parts.netloc:
                return f"{parts.scheme}://{parts.netloc}"
    return None


def school_urls(account: SchoolMpesaAccount) -> dict[str, str] | None:
    """The three addresses Safaricom should call for THIS school's paybill (each carries the school's own token)."""
    origin = public_origin()
    if not origin:
        return None
    token = school_webhook_token(account.school_id, account.callback_token_version)
    return {
        "stk_callback": f"{origin}{STK_CALLBACK_PATH}?token={token}",
        "c2b_validation": f"{origin}{C2B_VALIDATION_PATH}?token={token}",
        "c2b_confirmation": f"{origin}{C2B_CONFIRMATION_PATH}?token={token}",
    }


# --------------------------------------------------------------------------------------------------
# Which paybill does this school's STK push use?
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class MpesaChannel:
    credentials: MpesaCredentials
    callback_url: str | None  # None = the server doesn't know its own public address yet


def channel_for_school(school_id: str) -> MpesaChannel:
    """Raises MpesaNotAvailable (switched off / not set up) or MpesaConfigError (server-wide settings incomplete)."""
    with SystemSessionLocal() as db:
        mode = db.execute(select(School.mpesa_mode).where(School.id == school_id)).scalar_one_or_none()
        if mode == "GLOBAL":
            return MpesaChannel(global_credentials(), settings.mpesa_callback_url)
        if mode == "OWN":
            account = db.execute(select(SchoolMpesaAccount).where(SchoolMpesaAccount.school_id == school_id)).scalar_one_or_none()
            if account is None:
                raise MpesaNotAvailable()
            urls = school_urls(account)
            return MpesaChannel(credentials_from_account(account), urls["stk_callback"] if urls else None)
    raise MpesaNotAvailable()


def mpesa_enabled_for_school(school_id: str) -> bool:
    """For the frontend: should the "Pay with M-Pesa" button be shown? Never raises."""
    try:
        channel = channel_for_school(school_id)
    except (MpesaNotAvailable, MpesaConfigError):
        return False
    except Exception:  # noqa: BLE001 - e.g. a secret that no longer decrypts: the button is simply not offered
        logger.exception("Could not resolve M-Pesa for school %s", school_id)
        return False
    return channel.callback_url is not None


# --------------------------------------------------------------------------------------------------
# Paybill (C2B) payments: which school(s) can this belong to?
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class C2BRoute:
    school_ids: list[str]  # only these schools' students may be matched (empty = record it, match nobody)
    single_school_id: str | None  # set when exactly one school owns the paybill it was paid to
    shortcode: str


def route_c2b(db: Session, shortcode: str | int | None, token_school_id: str | None) -> C2BRoute | None:
    """None means "not ours, ignore it". Raises TokenScopeMismatch if a school's token is used for another school's
    paybill."""
    code = str(shortcode or "").strip()

    owned = []
    if code:
        owned = db.execute(
            select(SchoolMpesaAccount.school_id)
            .join(School, School.id == SchoolMpesaAccount.school_id)
            .where(SchoolMpesaAccount.shortcode == code, School.mpesa_mode == "OWN")
        ).scalars().all()

    if owned:
        if token_school_id is not None:
            if token_school_id not in owned:
                raise TokenScopeMismatch()
            owned = [token_school_id]  # the token names the school exactly, even if sandbox schools share a shortcode
        return C2BRoute(school_ids=list(owned), single_school_id=owned[0] if len(owned) == 1 else None, shortcode=code)

    if token_school_id is not None:
        return None  # a school's address, but that school has no live paybill on this shortcode

    global_code = str(settings.mpesa_shortcode or "").strip()
    if global_code and code and code != global_code:
        return None  # addressed to a paybill that isn't ours

    users_of_global = db.execute(select(School.id).where(School.mpesa_mode == "GLOBAL")).scalars().all()
    if not users_of_global and not global_code:
        return None  # no server-wide paybill is configured and no school uses one: this payment is not ours
    return C2BRoute(
        school_ids=list(users_of_global),
        single_school_id=users_of_global[0] if len(users_of_global) == 1 else None,
        shortcode=code,
    )

"""Platform operator: set up each school's own M-Pesa paybill. SUPER_ADMIN only.

What this does:
  * stores a school's Daraja key, secret and passkey ENCRYPTED (write-only: nothing here ever returns them),
  * checks the connection with Safaricom,
  * registers the school's own webhook addresses (carrying that school's token) for direct paybill payments,
  * switches a school between OFF / GLOBAL / OWN.

Secrets never appear in a response, a log line or an audit-log entry. Failures are reported with fixed messages,
never with Safaricom's raw reply, because that can echo what was sent.
"""

import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.database import get_system_db
from app.core.deps import CurrentUser, require_roles
from app.core.message_crypto import DecryptionError
from app.core.rate_limit import limiter
from app.models.mpesa_account import SchoolMpesaAccount
from app.models.school import School
from app.schemas.mpesa_account import MpesaAccountStatus, MpesaAccountUpdate, MpesaActionResult, MpesaModeUpdate
from app.services.audit_service import log_audit
from app.services.mpesa_accounts import credentials_from_account, encrypt_account_secret, public_origin, school_urls
from app.services.mpesa_service import MpesaConfigError, get_access_token, global_credentials, register_c2b_urls

logger = logging.getLogger("ledgr.mpesa")

router = APIRouter(prefix="/api/platform/schools/{school_id}/mpesa", tags=["platform"])

SUPER = require_roles("SUPER_ADMIN")

_SECRET_FIELDS = (("consumer_key", "consumer_key_enc"), ("consumer_secret", "consumer_secret_enc"), ("passkey", "passkey_enc"))


def _school(db: Session, school_id: str) -> School:
    school = db.get(School, school_id)
    if school is None:
        raise HTTPException(404, "School not found")
    return school


def _account(db: Session, school_id: str) -> SchoolMpesaAccount | None:
    return db.execute(select(SchoolMpesaAccount).where(SchoolMpesaAccount.school_id == school_id)).scalar_one_or_none()


def _global_configured() -> bool:
    try:
        global_credentials()
        return True
    except MpesaConfigError:
        return False


def _status(db: Session, school: School) -> MpesaAccountStatus:
    account = _account(db, school.id)
    others = db.execute(
        select(func.count()).select_from(School).where(School.mpesa_mode == "GLOBAL", School.id != school.id)
    ).scalar_one()
    return MpesaAccountStatus(
        school_id=school.id,
        mode=school.mpesa_mode,
        has_account=account is not None,
        environment=account.environment if account else None,
        shortcode=account.shortcode if account else None,
        tested_at=account.tested_at if account else None,
        c2b_registered_at=account.c2b_registered_at if account else None,
        last_error=account.last_error if account else None,
        global_configured=_global_configured(),
        addresses_ready=public_origin() is not None,
        other_schools_on_global=others,
    )


def _result(db: Session, school: School, ok: bool, message: str) -> MpesaActionResult:
    return MpesaActionResult(ok=ok, message=message, status=_status(db, school))


def _audit(db: Session, school: School, user: CurrentUser, action: str, **metadata) -> None:
    # Metadata is for humans reading the trail: environment, shortcode, mode. NEVER a secret.
    log_audit(db, school_id=school.id, action=action, entity_type="School", entity_id=school.id, user_id=user.user_id, metadata=metadata or None)


@router.get("", response_model=MpesaAccountStatus)
def get_mpesa_status(school_id: str, db: Session = Depends(get_system_db), _user: CurrentUser = Depends(SUPER)):
    return _status(db, _school(db, school_id))


@router.put("", response_model=MpesaActionResult)
@limiter.limit("30/minute")
def save_mpesa_account(
    request: Request,
    school_id: str,
    data: MpesaAccountUpdate,
    db: Session = Depends(get_system_db),
    user: CurrentUser = Depends(SUPER),
):
    school = _school(db, school_id)
    account = _account(db, school_id)

    supplied = {}
    for field_name, _col in _SECRET_FIELDS:
        value = (getattr(data, field_name) or "").strip()
        if value:
            if any(c.isspace() for c in value):
                raise HTTPException(422, f"The {field_name.replace('_', ' ')} must not contain spaces or line breaks. Copy it again.")
            supplied[field_name] = value

    if account is None:
        missing = [name.replace("_", " ") for name, _c in _SECRET_FIELDS if name not in supplied]
        if missing:
            raise HTTPException(422, f"Enter the {', '.join(missing)} (all three are needed the first time).")
        account = SchoolMpesaAccount(
            school_id=school_id, environment=data.environment, shortcode=data.shortcode,
            **{column: encrypt_account_secret(school_id, field_name, supplied[field_name]) for field_name, column in _SECRET_FIELDS},
        )
        db.add(account)
        changed = True
    else:
        changed = bool(supplied) or account.environment != data.environment or account.shortcode != data.shortcode
        account.environment = data.environment
        account.shortcode = data.shortcode
        for field_name, column in _SECRET_FIELDS:
            if field_name in supplied:
                setattr(account, column, encrypt_account_secret(school_id, field_name, supplied[field_name]))
    account.updated_by_user_id = user.user_id

    note = ""
    if changed:
        # Whatever was tested or registered before no longer describes what is saved.
        account.tested_at = None
        account.c2b_registered_at = None
        account.last_error = None
        if school.mpesa_mode == "OWN":
            school.mpesa_mode = "OFF"  # never leave payments live on details nobody has tested
            note = " M-Pesa for this school was switched OFF until you test the new details."

    _audit(db, school, user, "SCHOOL_MPESA_SAVED", environment=data.environment, shortcode=data.shortcode, secrets_replaced=sorted(supplied))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That paybill is already used by another school's live account.")
    db.refresh(school)
    return _result(db, school, True, "Saved." + note)


@router.delete("", response_model=MpesaActionResult)
@limiter.limit("30/minute")
def delete_mpesa_account(request: Request, school_id: str, db: Session = Depends(get_system_db), user: CurrentUser = Depends(SUPER)):
    school = _school(db, school_id)
    account = _account(db, school_id)
    if account is not None:
        db.delete(account)
    was = school.mpesa_mode
    if was == "OWN":
        school.mpesa_mode = "OFF"
    _audit(db, school, user, "SCHOOL_MPESA_REMOVED", previous_mode=was)
    db.commit()
    db.refresh(school)
    return _result(db, school, True, "The saved M-Pesa details were removed." + (" M-Pesa is now OFF for this school." if was == "OWN" else ""))


@router.post("/test", response_model=MpesaActionResult)
@limiter.limit("20/minute")
async def test_mpesa_connection(
    request: Request, school_id: str, db: Session = Depends(get_system_db), user: CurrentUser = Depends(SUPER)
):
    """Asks Safaricom for an access token with the saved key and secret. That proves the key and secret are right
    for the chosen environment. It cannot prove the shortcode or passkey: only a real payment does."""
    school = await run_in_threadpool(_school, db, school_id)
    account = await run_in_threadpool(_account, db, school_id)
    if account is None:
        raise HTTPException(409, "Save the school's M-Pesa details first.")
    try:
        creds = await run_in_threadpool(credentials_from_account, account)
    except DecryptionError:
        raise HTTPException(409, "The saved details can't be read (the encryption key has changed). Enter them again.")

    ok, message = True, "Connected. Safaricom accepted the key and secret."
    try:
        await get_access_token(creds)
    except httpx.HTTPStatusError as exc:
        ok = False
        message = (
            "Safaricom rejected the consumer key and secret for the "
            f"{'live' if account.environment == 'PRODUCTION' else 'sandbox'} environment. "
            "Check they were copied exactly and belong to that environment."
            if exc.response.status_code in (400, 401, 403)
            else f"Safaricom answered with an error ({exc.response.status_code}). Try again shortly."
        )
    except (httpx.TransportError, httpx.TimeoutException):
        ok, message = False, "Couldn't reach Safaricom. Try again in a moment."
    except Exception:  # noqa: BLE001 - never echo what the failure carried
        logger.exception("M-Pesa connection test failed for school %s", school_id)
        ok, message = False, "The connection test failed. See the server logs."

    account.tested_at = datetime.now(timezone.utc) if ok else None
    account.last_error = None if ok else message
    await run_in_threadpool(_audit, db, school, user, "SCHOOL_MPESA_TESTED", ok=ok, environment=account.environment)
    await run_in_threadpool(db.commit)
    await run_in_threadpool(db.refresh, school)
    return await run_in_threadpool(_result, db, school, ok, message)


@router.post("/register-urls", response_model=MpesaActionResult)
@limiter.limit("20/minute")
async def register_mpesa_urls(
    request: Request, school_id: str, db: Session = Depends(get_system_db), user: CurrentUser = Depends(SUPER)
):
    """Tells Safaricom to send this school's direct paybill payments to Ledgr, on addresses that carry this school's
    own token. STK pushes need no registration: their address travels with each request."""
    school = await run_in_threadpool(_school, db, school_id)
    account = await run_in_threadpool(_account, db, school_id)
    if account is None:
        raise HTTPException(409, "Save the school's M-Pesa details first.")
    urls = school_urls(account)
    if urls is None:
        raise HTTPException(409, "The server doesn't know its own public address yet. Set MPESA_CALLBACK_URL on the server first.")
    if not urls["c2b_confirmation"].startswith("https://"):
        raise HTTPException(409, "Safaricom only calls public https addresses. The server's public address must start with https://")
    try:
        creds = await run_in_threadpool(credentials_from_account, account)
    except DecryptionError:
        raise HTTPException(409, "The saved details can't be read (the encryption key has changed). Enter them again.")

    ok, message = True, "Registered. Safaricom will now send this paybill's direct payments to Ledgr."
    try:
        await register_c2b_urls(creds, urls["c2b_validation"], urls["c2b_confirmation"])
    except httpx.HTTPStatusError:
        ok, message = False, "Safaricom refused the key and secret. Run the connection test first."
    except (httpx.TransportError, httpx.TimeoutException):
        ok, message = False, "Couldn't reach Safaricom. Try again in a moment."
    except RuntimeError as exc:
        # The text carries Safaricom's reply (useful to the operator in the server log, not in the response).
        logger.error("C2B registration refused for school %s: %s", school_id, exc)
        ok, message = False, "Safaricom refused the registration. Check the shortcode belongs to these credentials and that C2B is enabled for it."
    except Exception:  # noqa: BLE001
        logger.exception("C2B registration failed for school %s", school_id)
        ok, message = False, "The registration failed. See the server logs."

    account.c2b_registered_at = datetime.now(timezone.utc) if ok else account.c2b_registered_at
    account.last_error = None if ok else message
    await run_in_threadpool(_audit, db, school, user, "SCHOOL_MPESA_URLS_REGISTERED", ok=ok, shortcode=account.shortcode)
    await run_in_threadpool(db.commit)
    await run_in_threadpool(db.refresh, school)
    return await run_in_threadpool(_result, db, school, ok, message)


@router.post("/mode", response_model=MpesaActionResult)
@limiter.limit("30/minute")
def set_mpesa_mode(
    request: Request,
    school_id: str,
    data: MpesaModeUpdate,
    db: Session = Depends(get_system_db),
    user: CurrentUser = Depends(SUPER),
):
    """OFF: no online M-Pesa. GLOBAL: the server-wide paybill. OWN: the school's own paybill (it must have been
    tested first, so payments are never switched on against details nobody has tried)."""
    school = _school(db, school_id)
    account = _account(db, school_id)
    warning = ""

    if data.mode == "OWN":
        if account is None:
            raise HTTPException(409, "Save the school's own M-Pesa details first.")
        if account.tested_at is None:
            raise HTTPException(409, "Test the connection first, then switch it on.")
    elif data.mode == "GLOBAL":
        if not _global_configured():
            raise HTTPException(409, "The server-wide M-Pesa settings (MPESA_*) are not complete.")
        others = db.execute(select(func.count()).select_from(School).where(School.mpesa_mode == "GLOBAL", School.id != school_id)).scalar_one()
        if others:
            warning = (
                f" Note: {others} other school(s) also use the server-wide paybill, so their parents pay into the same account "
                "and direct payments with the same admission number can't be told apart."
            )

    previous = school.mpesa_mode
    school.mpesa_mode = data.mode
    _audit(db, school, user, "SCHOOL_MPESA_MODE_CHANGED", previous=previous, mode=data.mode)
    db.commit()
    db.refresh(school)
    labels = {"OFF": "switched off", "GLOBAL": "set to the server-wide paybill", "OWN": "set to the school's own paybill"}
    return _result(db, school, True, f"M-Pesa for this school is {labels[data.mode]}.{warning}")

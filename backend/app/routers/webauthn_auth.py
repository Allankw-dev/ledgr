import secrets
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

import webauthn
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
)
from webauthn.helpers.exceptions import InvalidRegistrationResponse, InvalidAuthenticationResponse
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db, get_system_db
from app.core.deps import get_current_user, get_school_scope, CurrentUser
from app.core.config import settings
from app.core.rate_limit import limiter
from app.models.school import User
from app.models.webauthn import WebAuthnCredential, WebAuthnChallenge
from app.schemas.auth import TokenResponse
from app.schemas.webauthn import (
    WebAuthnRegisterOptionsResponse,
    WebAuthnRegisterVerifyRequest,
    WebAuthnLoginOptionsResponse,
    WebAuthnLoginVerifyRequest,
    WebAuthnCredentialResponse,
)
from app.routers.auth import _build_token_response

router = APIRouter(prefix="/api/auth/webauthn", tags=["webauthn"])

CHALLENGE_TTL_MINUTES = 5


@dataclass
class ConsumedChallenge:
    """A plain snapshot of the values we need, captured before the DB row
    is deleted — reading attributes off a SQLAlchemy object after it's been
    deleted-and-committed risks a re-fetch against a row that no longer
    exists, so we pull out exactly what's needed first."""

    challenge: bytes
    user_id: str | None


def _store_challenge(db: Session, challenge: bytes, purpose: str, user_id: str | None) -> str:
    row = WebAuthnChallenge(
        user_id=user_id,
        challenge=challenge,
        purpose=purpose,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=CHALLENGE_TTL_MINUTES),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.id


def _consume_challenge(db: Session, challenge_id: str, purpose: str) -> ConsumedChallenge:
    """Single-use by design — fetched and immediately deleted, so a
    captured/replayed verify request can never succeed twice against the
    same challenge, and expired challenges are rejected outright."""
    row = db.get(WebAuthnChallenge, challenge_id)
    if not row or row.purpose != purpose:
        raise HTTPException(400, "This verification request has expired or is invalid. Please try again.")
    if row.expires_at < datetime.now(timezone.utc):
        db.delete(row)
        db.commit()
        raise HTTPException(400, "This verification request has expired. Please try again.")

    snapshot = ConsumedChallenge(challenge=row.challenge, user_id=row.user_id)
    db.delete(row)
    db.commit()
    return snapshot


@router.post("/register/options", response_model=WebAuthnRegisterOptionsResponse)
@limiter.limit("10/minute")
def register_options(
    request: Request,
    db: Session = Depends(get_db),
    school_id: str = Depends(get_school_scope),
    user: CurrentUser = Depends(get_current_user),
):
    """Enrolling a NEW fingerprint requires already being logged in the
    normal way first — this is "add a fingerprint to my account", not a
    standalone signup path. resident_key=REQUIRED is what makes the
    credential discoverable later, so login can work without typing an
    email first."""
    db_user = db.get(User, user.user_id)
    if not db_user:
        raise HTTPException(404, "User not found")

    existing = db.execute(
        select(WebAuthnCredential.credential_id).where(WebAuthnCredential.user_id == user.user_id)
    ).scalars().all()

    options = webauthn.generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_name=db_user.email,
        user_id=db_user.id.encode("utf-8"),
        user_display_name=db_user.full_name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=webauthn.base64url_to_bytes(cid)) for cid in existing
        ],
    )

    challenge_id = _store_challenge(db, options.challenge, "registration", user.user_id)
    return WebAuthnRegisterOptionsResponse(options=webauthn.helpers.options_to_json_dict(options), challenge_id=challenge_id)


@router.post("/register/verify", response_model=WebAuthnCredentialResponse, status_code=201)
@limiter.limit("10/minute")
def register_verify(
    request: Request,
    data: WebAuthnRegisterVerifyRequest,
    db: Session = Depends(get_db),
    _school_id: str = Depends(get_school_scope),
    user: CurrentUser = Depends(get_current_user),
):
    consumed = _consume_challenge(db, data.challenge_id, "registration")
    if consumed.user_id != user.user_id:
        raise HTTPException(403, "This verification request belongs to a different account.")

    try:
        verified = webauthn.verify_registration_response(
            credential=data.credential,
            expected_challenge=consumed.challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.frontend_url,
        )
    except InvalidRegistrationResponse:
        raise HTTPException(400, "Couldn't verify that fingerprint. Please try again.")

    credential = WebAuthnCredential(
        user_id=user.user_id,
        credential_id=webauthn.helpers.bytes_to_base64url(verified.credential_id),
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        device_name=data.device_name,
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)

    return WebAuthnCredentialResponse(
        id=credential.id,
        device_name=credential.device_name,
        created_at=credential.created_at,
        last_used_at=credential.last_used_at,
    )


@router.get("/credentials", response_model=list[WebAuthnCredentialResponse])
def list_credentials(
    db: Session = Depends(get_db),
    _school_id: str = Depends(get_school_scope),
    user: CurrentUser = Depends(get_current_user),
):
    rows = db.execute(
        select(WebAuthnCredential)
        .where(WebAuthnCredential.user_id == user.user_id)
        .order_by(WebAuthnCredential.created_at.desc())
    ).scalars().all()
    return [
        WebAuthnCredentialResponse(id=r.id, device_name=r.device_name, created_at=r.created_at, last_used_at=r.last_used_at)
        for r in rows
    ]


@router.delete("/credentials/{credential_id}", status_code=204)
def delete_credential(
    credential_id: str,
    db: Session = Depends(get_db),
    _school_id: str = Depends(get_school_scope),
    user: CurrentUser = Depends(get_current_user),
):
    row = db.execute(
        select(WebAuthnCredential).where(
            WebAuthnCredential.id == credential_id, WebAuthnCredential.user_id == user.user_id
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Fingerprint credential not found")
    db.delete(row)
    db.commit()


@router.post("/login/options", response_model=WebAuthnLoginOptionsResponse)
@limiter.limit("15/minute")
def login_options(request: Request, db: Session = Depends(get_system_db)):
    """Public, pre-auth — no allow_credentials means the browser presents
    whichever discoverable (resident-key) credentials it has for this
    site, so signing in doesn't require typing an email first. We
    genuinely don't know who's signing in until their authenticator's
    response comes back with a credential_id we can look up."""
    challenge = secrets.token_bytes(32)
    options = webauthn.generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        challenge=challenge,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    challenge_id = _store_challenge(db, challenge, "authentication", None)
    return WebAuthnLoginOptionsResponse(options=webauthn.helpers.options_to_json_dict(options), challenge_id=challenge_id)


@router.post("/login/verify", response_model=TokenResponse)
@limiter.limit("15/minute")
def login_verify(request: Request, data: WebAuthnLoginVerifyRequest, db: Session = Depends(get_system_db)):
    consumed = _consume_challenge(db, data.challenge_id, "authentication")

    raw_credential_id = data.credential.get("id")
    if not raw_credential_id:
        raise HTTPException(400, "Malformed fingerprint response.")

    stored = db.execute(
        select(WebAuthnCredential).where(WebAuthnCredential.credential_id == raw_credential_id)
    ).scalar_one_or_none()
    if not stored:
        raise HTTPException(401, "That fingerprint isn't registered on any account here.")

    user = db.get(User, stored.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "This account is no longer active.")

    try:
        verified = webauthn.verify_authentication_response(
            credential=data.credential,
            expected_challenge=consumed.challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.frontend_url,
            credential_public_key=stored.public_key,
            credential_current_sign_count=stored.sign_count,
        )
    except InvalidAuthenticationResponse:
        raise HTTPException(401, "Couldn't verify that fingerprint. Please try again.")

    # Fingerprint auth (user_verification=required) is itself a strong,
    # verified-presence factor, so this deliberately skips straight to
    # issuing a token rather than also routing through the TOTP 2FA gate
    # _complete_login applies to password logins — requiring a second
    # extra factor on top of a biometric would just be friction, not
    # additional real security.
    stored.sign_count = verified.new_sign_count
    stored.last_used_at = datetime.now(timezone.utc)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return _build_token_response(db, user)

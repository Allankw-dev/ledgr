from typing import Union
from datetime import datetime, timezone
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from app.core.config import settings
from app.core.database import get_system_db
from app.core.deps import invalidate_user_state
from app.core.phone import normalize_phone, phone_key
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_2fa_challenge_token,
    decode_2fa_challenge_token,
    create_password_reset_token,
    decode_password_reset_token,
    create_email_change_token,
    decode_email_change_token,
    _email_fingerprint,
)
from app.core.totp import generate_totp_secret, get_provisioning_uri, verify_totp_code
from app.core.rate_limit import limiter
from app.core.deps import get_current_user, require_roles, CurrentUser
from app.services.notification_service import send_email, send_sms, NotificationConfigError
from app.services.audit_service import log_audit
from app.services.refresh_token_service import (
    issue_refresh_token,
    rotate_refresh_token,
    revoke_token_family,
    revoke_all_for_user,
)
from app.schemas.auth import (
    RegisterSchoolRequest,
    LoginRequest,
    GoogleAuthRequest,
    TokenResponse,
    TwoFactorRequiredResponse,
    TwoFactorSetupResponse,
    TwoFactorEnableRequest,
    TwoFactorDisableRequest,
    TwoFactorVerifyLoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ForgotPasswordResponse,
    RefreshRequest,
    EmailChangeRequest,
    EmailChangeConfirmRequest,
)
from app.models.school import School, User
from app.models.enums import UserRole

from app.schemas.guardian_request import RegisterParentRequest
from app.models.school import School, User
from app.models.enums import UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/setup-status")
def get_setup_status(db: Session = Depends(get_system_db)):
    """
    Public, unauthenticated — lets the frontend check whether this Ledgr
    instance already has its one school set up, before even showing the
    registration form. Reveals nothing sensitive (not the school's name,
    just whether setup has happened), so it's safe to leave unauthenticated.
    """
    is_set_up = db.query(School).first() is not None
    return {"is_set_up": is_set_up}


@router.post("/register-parent", response_model=TokenResponse, status_code=201)
@limiter.limit("5/minute")
def register_parent(request: Request, data: RegisterParentRequest, db: Session = Depends(get_system_db)):
    """
    Public self-signup for a parent. Deliberately creates ONLY the account
    here — no student link yet. Linking happens as a separate, explicit
    step (POST /api/students/{id}/request-link) that starts PENDING and
    needs a bursar's approval, because a parent typing in an admission
    number they saw on a report card or uniform is a much weaker proof of
    identity than a bursar creating the link from the actual student record.
    """
    school = db.query(School).first()
    if not school:
        raise HTTPException(503, "This school hasn't been set up yet. Contact the school office.")

    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(409, "An account with this email already exists")

    parent = User(
        school_id=school.id,
        email=data.email,
        password_hash=hash_password(data.password),
        role=UserRole.PARENT,
        full_name=data.full_name,
    )
    db.add(parent)
    db.commit()
    db.refresh(parent)

    return _build_token_response(db, parent)


def _find_user_by_identifier(db: Session, identifier: str) -> User | None:
    """Used by password RESET. An email address, or — for teachers only — a
    phone number. Phone-number reset is deliberately limited to teachers: their
    numbers are entered (and so known to be right) by the school admin, whereas
    a parent's number is self-entered and unverified — a typo'd number would
    otherwise let a stranger who owns it request a reset link for that account."""
    identifier = identifier.strip()
    if "@" in identifier:
        return db.query(User).filter(User.email == identifier).first()
    phone = normalize_phone(identifier)
    if not phone:
        return None
    return db.query(User).filter(User.phone == phone, User.role == UserRole.TEACHER).first()


_MAX_PHONE_CANDIDATES = 5
_dummy_hash: str | None = None


def _burn_password_check(password: str) -> None:
    """Spend the same time a real password check would when there's no such
    account, so response time doesn't reveal which emails/numbers are registered."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("not-a-real-password")
    verify_password(password, _dummy_hash)


def _authenticate(db: Session, identifier: str, password: str) -> User | None:
    """Email OR phone number + password, for every role.

    A phone number can legitimately be on more than one account (two parents
    sharing a phone, a parent who is also a teacher, ...), so a phone sign-in
    checks the password against each active account with that number and
    succeeds only if exactly ONE matches. That keeps the failure message
    identical for "no such number", "wrong password" and "ambiguous".
    """
    identifier = identifier.strip()
    if "@" in identifier:
        candidates = [u for u in [db.query(User).filter(User.email == identifier).first()] if u]
    else:
        key = phone_key(identifier)
        candidates = (
            db.query(User)
            .filter(func.ledgr_phone_key(User.phone) == key, User.is_active.is_(True))
            .order_by(User.created_at)
            .limit(_MAX_PHONE_CANDIDATES)
            .all()
            if key
            else []
        )

    if not candidates:
        _burn_password_check(password)
        return None
    matches = [u for u in candidates if u.is_active and verify_password(password, u.password_hash)]
    return matches[0] if len(matches) == 1 else None


def _token_response(user: User, refresh_token: str, school_name: str | None = None) -> TokenResponse:
    token = create_access_token(user.id, user.school_id, user.role.value, user.token_version or 0)
    return TokenResponse(
        token=token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "school_id": user.school_id,
        },
        school={"id": user.school_id, "name": school_name} if school_name else None,
    )


def _build_token_response(db: Session, user: User, school_name: str | None = None) -> TokenResponse:
    """A fresh sign-in: short-lived access token + a new refresh-token family."""
    return _token_response(user, issue_refresh_token(db, user), school_name)


@router.post("/register-school", response_model=TokenResponse, status_code=201)
@limiter.limit("5/minute")
def register_school(request: Request, data: RegisterSchoolRequest, db: Session = Depends(get_system_db)):
    """
    Onboards THE school + its first SCHOOL_ADMIN user — singular, deliberately.
    This Ledgr instance is built for one specific school, not a multi-tenant
    platform, so once a school exists this endpoint permanently refuses to
    create a second one. That check runs before anything else and is not
    conditional on who's calling — an already-set-up instance rejects this
    request from anyone, authenticated or not, forever.
    """
    if db.query(School).first() is not None:
        raise HTTPException(
            403,
            "This Ledgr instance is already set up for a school. If you need a bursar or "
            "admin account, ask your school's existing administrator to create one for you.",
        )

    existing = db.query(User).filter(User.email == data.admin_email).first()
    if existing:
        raise HTTPException(409, "An account with this email already exists")

    school = School(
        name=data.school_name,
        country=data.country.upper(),
        currency=data.currency.upper(),
        contact_email=data.admin_email,
    )
    db.add(school)
    db.flush()

    admin = User(
        school_id=school.id,
        email=data.admin_email,
        password_hash=hash_password(data.admin_password),
        role=UserRole.SCHOOL_ADMIN,
        full_name=data.admin_full_name,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    db.refresh(school)

    return _build_token_response(db, admin, school.name)


def _complete_login(user: User, db: Session) -> Union[TokenResponse, TwoFactorRequiredResponse]:
    """Shared by password login and Google sign-in — once we know WHO the
    user is and that they're allowed in, the rest (2FA gate, last_login_at,
    issuing our own JWT) is identical regardless of how they proved it."""
    if user.totp_enabled:
        return TwoFactorRequiredResponse(challenge_token=create_2fa_challenge_token(user.id))

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return _build_token_response(db, user)


@router.post("/login", response_model=Union[TokenResponse, TwoFactorRequiredResponse])
@limiter.limit("10/minute")
def login(request: Request, data: LoginRequest, db: Session = Depends(get_system_db)):
    user = _authenticate(db, data.email, data.password)
    if not user:
        raise HTTPException(401, "Invalid email/phone or password")

    return _complete_login(user, db)


@router.post("/google", response_model=Union[TokenResponse, TwoFactorRequiredResponse])
@limiter.limit("10/minute")
def google_auth(request: Request, data: GoogleAuthRequest, db: Session = Depends(get_system_db)):
    """Verifies the ID token Google's Sign In button hands back to the
    frontend, then either logs in a matching existing account or — for a
    brand-new email — self-registers a PARENT the same way register-parent
    does. Staff accounts (BURSAR/SCHOOL_ADMIN) are never auto-created here;
    Google can only ever be a login method for those, not a signup path,
    same reasoning as why there's no public staff-signup endpoint at all."""
    if not settings.google_client_id:
        raise HTTPException(503, "Google sign-in isn't configured for this school yet.")

    try:
        idinfo = google_id_token.verify_oauth2_token(
            data.credential, google_requests.Request(), audience=settings.google_client_id
        )
    except ValueError:
        raise HTTPException(401, "Could not verify that Google sign-in. Please try again.")

    if not idinfo.get("email_verified"):
        raise HTTPException(401, "Your Google account's email isn't verified. Please use a verified Google account.")

    email = idinfo["email"]
    user = db.query(User).filter(User.email == email).first()

    if user:
        if not user.is_active:
            raise HTTPException(401, "This account has been deactivated. Contact your school office.")
        return _complete_login(user, db)

    # No matching account — self-register as a parent, mirroring register-parent.
    school = db.query(School).first()
    if not school:
        raise HTTPException(503, "This school hasn't been set up yet. Contact the school office.")

    full_name = idinfo.get("name") or email.split("@")[0]
    new_user = User(
        school_id=school.id,
        email=email,
        # Random, never issued to anyone — a Google-only account simply has
        # no working password until/unless the person sets one separately.
        password_hash=hash_password(secrets.token_urlsafe(32)),
        role=UserRole.PARENT,
        full_name=full_name,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return _complete_login(new_user, db)


@router.post("/2fa/verify-login", response_model=TokenResponse)
@limiter.limit("10/minute")
def verify_login(request: Request, data: TwoFactorVerifyLoginRequest, db: Session = Depends(get_system_db)):
    """Second step of login for accounts with 2FA enabled."""
    try:
        user_id = decode_2fa_challenge_token(data.challenge_token)
    except ValueError:
        raise HTTPException(401, "This login attempt has expired. Please sign in again.")

    user = db.get(User, user_id)
    if not user or not user.is_active or not user.totp_secret:
        raise HTTPException(401, "Invalid login attempt")

    if not verify_totp_code(user.totp_secret, data.code):
        raise HTTPException(401, "Incorrect code. Check your authenticator app and try again.")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return _build_token_response(db, user)


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
def setup_2fa(
    db: Session = Depends(get_system_db),
    user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    """
    Generates a new TOTP secret and returns the provisioning URI to render
    as a QR code. Storing the secret here does NOT enable 2FA yet — that
    only happens once /2fa/enable confirms the user can generate a valid
    code, so a half-finished setup can never lock someone out.
    """
    db_user = db.get(User, user.user_id)
    if not db_user:
        raise HTTPException(404, "User not found")

    secret = generate_totp_secret()
    db_user.totp_secret = secret
    db.commit()

    return TwoFactorSetupResponse(
        secret=secret,
        provisioning_uri=get_provisioning_uri(secret, db_user.email),
    )


@router.post("/2fa/enable")
def enable_2fa(
    data: TwoFactorEnableRequest,
    db: Session = Depends(get_system_db),
    user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    db_user = db.get(User, user.user_id)
    if not db_user or not db_user.totp_secret:
        raise HTTPException(400, "Call /2fa/setup first to generate a secret")

    if not verify_totp_code(db_user.totp_secret, data.code):
        raise HTTPException(401, "Incorrect code. Check your authenticator app and try again.")

    db_user.totp_enabled = True
    db.commit()
    return {"enabled": True}


@router.post("/2fa/disable")
def disable_2fa(
    data: TwoFactorDisableRequest,
    db: Session = Depends(get_system_db),
    user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    db_user = db.get(User, user.user_id)
    if not db_user:
        raise HTTPException(404, "User not found")

    if not verify_password(data.password, db_user.password_hash):
        raise HTTPException(401, "Incorrect password")

    db_user.totp_enabled = False
    db_user.totp_secret = None
    db.commit()
    return {"enabled": False}


@router.get("/2fa/status")
def get_2fa_status(db: Session = Depends(get_system_db), user: CurrentUser = Depends(get_current_user)):
    db_user = db.get(User, user.user_id)
    if not db_user:
        raise HTTPException(404, "User not found")
    return {"enabled": db_user.totp_enabled}


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
@limiter.limit("5/minute")
def forgot_password(request: Request, data: ForgotPasswordRequest, db: Session = Depends(get_system_db)):
    """Always returns the same generic response whether or not the email
    is registered — an attacker enumerating emails shouldn't be able to
    tell the difference. The actual reset link is only ever sent by email,
    never returned in the response body."""
    user = _find_user_by_identifier(db, data.email)
    if user and user.is_active:
        token = create_password_reset_token(user.id, user.password_hash)
        reset_link = f"{settings.frontend_url}/reset-password?token={token}"
        has_real_email = not user.email.endswith("@phone.ledgr.invalid")
        if has_real_email:
            try:
                send_email(
                    user.email,
                    "Reset your Ledgr password",
                    f"Hi {user.full_name},\n\n"
                    f"Click the link below to reset your password. This link expires in 30 minutes "
                    f"and can only be used once:\n\n{reset_link}\n\n"
                    f"If you didn't request this, you can safely ignore this email.",
                )
            except NotificationConfigError:
                # Email isn't configured on this deployment — fail quietly from
                # the user's perspective (same generic response either way) but
                # this is worth knowing about server-side.
                pass
        if user.phone and user.role == UserRole.TEACHER and "@" not in data.email.strip():
            # Phone-based reset: only when they asked by phone number.
            try:
                send_sms(user.phone, f"Ledgr password reset (valid 30 min, one use): {reset_link}")
            except NotificationConfigError:
                pass
    return ForgotPasswordResponse()


@router.post("/reset-password")
@limiter.limit("10/minute")
def reset_password(request: Request, data: ResetPasswordRequest, db: Session = Depends(get_system_db)):
    # We need a user to check the token's password fingerprint against, but
    # the token doesn't tell us who it's for until we decode it — and we
    # can't decode it without a hash to compare. So decode first without
    # verifying the fingerprint match, load that user, then verify.
    from jose import jwt, JWTError

    try:
        unverified = jwt.decode(
            data.token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        raise HTTPException(400, "Invalid or expired reset link")

    user = db.get(User, unverified.get("sub"))
    if not user:
        raise HTTPException(400, "Invalid or expired reset link")

    try:
        decode_password_reset_token(data.token, user.password_hash)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    user.password_hash = hash_password(data.new_password)
    # Sign the user out of every existing session: any token issued before
    # this reset carries the old version and is rejected by get_current_user.
    user.token_version = (user.token_version or 0) + 1
    revoke_all_for_user(db, user.id)
    db.commit()
    invalidate_user_state(user.id)
    return {"reset": True}


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("60/minute")
def refresh_session(request: Request, data: RefreshRequest, db: Session = Depends(get_system_db)):
    """Swap a refresh token for a new access token + a new refresh token. The
    old refresh token is single-use — see services/refresh_token_service.py."""
    result = rotate_refresh_token(db, data.refresh_token)
    if result is None:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    user, new_refresh = result
    return _token_response(user, new_refresh)


@router.post("/logout")
@limiter.limit("60/minute")
def logout(request: Request, data: RefreshRequest, db: Session = Depends(get_system_db)):
    """Ends this device's session for good. Idempotent and always 200 — the
    caller is signing out either way, and it shouldn't learn anything about tokens."""
    revoke_token_family(db, data.refresh_token)
    return {"ok": True}


# --- Parent changes their own sign-in email ----------------------------------
# Covers "I lost access to the email I signed up with". Two proofs are needed:
# the current password (someone on an unlocked, already-signed-in phone can't
# redirect the account) and a link that only works from the NEW inbox (so a
# typo, or someone else's address, can't be attached to the account).

_PLACEHOLDER_EMAIL_DOMAIN = "@phone.ledgr.invalid"


@router.post("/email-change/request")
@limiter.limit("5/minute")
def request_email_change(
    request: Request,
    data: EmailChangeRequest,
    db: Session = Depends(get_system_db),
    user: CurrentUser = Depends(require_roles("PARENT")),
):
    db_user = db.get(User, user.user_id)
    if not db_user:
        raise HTTPException(404, "User not found")

    if not verify_password(data.password, db_user.password_hash):
        raise HTTPException(401, "Incorrect password")

    new_email = data.new_email.strip()
    if new_email.lower().endswith(_PLACEHOLDER_EMAIL_DOMAIN):
        raise HTTPException(422, "Please enter a real email address.")
    if new_email.lower() == db_user.email.lower():
        raise HTTPException(400, "That's already your email address.")
    taken = db.query(User.id).filter(func.lower(User.email) == new_email.lower(), User.id != db_user.id).first()
    if taken:
        raise HTTPException(409, "That email is already used by another account.")

    token = create_email_change_token(db_user.id, db_user.email, new_email)
    link = f"{settings.frontend_url}/confirm-email?token={token}"
    try:
        send_email(
            new_email,
            "Confirm your new Ledgr email",
            f"Hi {db_user.full_name},\n\n"
            f"Someone asked to use this address as the sign-in email for a Ledgr parent account. "
            f"To confirm it's you, open the link below. It expires in "
            f"{settings.email_change_expires_minutes} minutes and only works once:\n\n{link}\n\n"
            f"If you didn't ask for this, ignore this email — nothing will change.",
        )
    except NotificationConfigError:
        # Unlike forgot-password, this must NOT pretend it worked: the parent is
        # signed in and waiting on a link that will never arrive.
        raise HTTPException(503, "Email isn't set up for this school yet, so we can't send the confirmation link. Contact the school office.")

    return {"message": f"We sent a confirmation link to {new_email}. It expires in {settings.email_change_expires_minutes} minutes."}


@router.post("/email-change/confirm")
@limiter.limit("10/minute")
def confirm_email_change(request: Request, data: EmailChangeConfirmRequest, db: Session = Depends(get_system_db)):
    """Public on purpose — the link is opened from the new inbox, possibly on
    a different device than the one signed in. The signed token is the proof."""
    try:
        user_id, new_email, current_fp = decode_email_change_token(data.token)
    except ValueError:
        raise HTTPException(400, "This link is invalid or has expired. Request the change again from your profile.")

    db_user = db.get(User, user_id)
    if not db_user or not db_user.is_active or db_user.role != UserRole.PARENT:
        raise HTTPException(400, "This link is invalid or has expired. Request the change again from your profile.")
    if _email_fingerprint(db_user.email) != current_fp:
        raise HTTPException(400, "This link has already been used or is out of date.")
    if db.query(User.id).filter(func.lower(User.email) == new_email.lower(), User.id != db_user.id).first():
        raise HTTPException(409, "That email is already used by another account.")

    old_email = db_user.email
    db_user.email = new_email
    # An email change is a credential change: sign out every existing session
    # (access tokens via token_version, refresh tokens explicitly).
    db_user.token_version = (db_user.token_version or 0) + 1
    revoke_all_for_user(db, db_user.id)
    if db_user.school_id:
        log_audit(
            db,
            school_id=db_user.school_id,
            action="USER_EMAIL_CHANGED",
            entity_type="User",
            entity_id=db_user.id,
            user_id=db_user.id,
            metadata={"old_email": old_email, "new_email": new_email},
        )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "That email is already used by another account.")
    invalidate_user_state(db_user.id)

    # Tell the old address, if it was a real one, so a hijack doesn't go unnoticed.
    if not old_email.lower().endswith(_PLACEHOLDER_EMAIL_DOMAIN):
        try:
            send_email(
                old_email,
                "Your Ledgr sign-in email was changed",
                f"Hi {db_user.full_name},\n\nThe sign-in email on your Ledgr parent account was changed to {new_email}. "
                f"If this was you, nothing more to do. If it wasn't, contact the school office right away.",
            )
        except Exception:  # best-effort notice; never undo a confirmed change
            logger.warning("Could not send email-change notice to previous address", exc_info=True)

    return {"changed": True, "email": new_email}

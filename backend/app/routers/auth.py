from typing import Union
from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from app.core.config import settings
from app.core.database import get_system_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_2fa_challenge_token,
    decode_2fa_challenge_token,
    create_password_reset_token,
    decode_password_reset_token,
)
from app.core.totp import generate_totp_secret, get_provisioning_uri, verify_totp_code
from app.core.rate_limit import limiter
from app.core.deps import get_current_user, require_roles, CurrentUser
from app.services.notification_service import send_email, NotificationConfigError
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
)
from app.models.school import School, User
from app.models.enums import UserRole

from app.schemas.guardian_request import RegisterParentRequest
from app.models.school import School, User
from app.models.enums import UserRole

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

    return _build_token_response(parent)


def _build_token_response(user: User, school_name: str | None = None) -> TokenResponse:
    token = create_access_token(user.id, user.school_id, user.role.value)
    return TokenResponse(
        token=token,
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "school_id": user.school_id,
        },
        school={"id": user.school_id, "name": school_name} if school_name else None,
    )


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

    return _build_token_response(admin, school.name)


def _complete_login(user: User, db: Session) -> Union[TokenResponse, TwoFactorRequiredResponse]:
    """Shared by password login and Google sign-in — once we know WHO the
    user is and that they're allowed in, the rest (2FA gate, last_login_at,
    issuing our own JWT) is identical regardless of how they proved it."""
    if user.totp_enabled:
        return TwoFactorRequiredResponse(challenge_token=create_2fa_challenge_token(user.id))

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return _build_token_response(user)


@router.post("/login", response_model=Union[TokenResponse, TwoFactorRequiredResponse])
@limiter.limit("10/minute")
def login(request: Request, data: LoginRequest, db: Session = Depends(get_system_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")

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

    return _build_token_response(user)


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
    user = db.query(User).filter(User.email == data.email).first()
    if user and user.is_active:
        token = create_password_reset_token(user.id, user.password_hash)
        reset_link = f"{settings.frontend_url}/reset-password?token={token}"
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
    db.commit()
    return {"reset": True}

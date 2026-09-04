from typing import Union
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_2fa_challenge_token,
    decode_2fa_challenge_token,
)
from app.core.totp import generate_totp_secret, get_provisioning_uri, verify_totp_code
from app.core.rate_limit import limiter
from app.core.deps import get_current_user, require_roles, CurrentUser
from app.schemas.auth import (
    RegisterSchoolRequest,
    LoginRequest,
    TokenResponse,
    TwoFactorRequiredResponse,
    TwoFactorSetupResponse,
    TwoFactorEnableRequest,
    TwoFactorDisableRequest,
    TwoFactorVerifyLoginRequest,
)
from app.models.school import School, User
from app.models.enums import UserRole

from app.schemas.guardian_request import RegisterParentRequest
from app.models.school import School, User
from app.models.enums import UserRole

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/setup-status")
def get_setup_status(db: Session = Depends(get_db)):
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
def register_parent(request: Request, data: RegisterParentRequest, db: Session = Depends(get_db)):
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
def register_school(request: Request, data: RegisterSchoolRequest, db: Session = Depends(get_db)):
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


@router.post("/login", response_model=Union[TokenResponse, TwoFactorRequiredResponse])
@limiter.limit("10/minute")
def login(request: Request, data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")

    if user.totp_enabled:
        # Correct password, but not done yet — hand back a short-lived
        # challenge token instead of a real one. last_login_at is updated
        # only once the code is verified too, in verify_login below.
        return TwoFactorRequiredResponse(challenge_token=create_2fa_challenge_token(user.id))

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return _build_token_response(user)


@router.post("/2fa/verify-login", response_model=TokenResponse)
@limiter.limit("10/minute")
def verify_login(request: Request, data: TwoFactorVerifyLoginRequest, db: Session = Depends(get_db)):
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
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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
def get_2fa_status(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    db_user = db.get(User, user.user_id)
    if not db_user:
        raise HTTPException(404, "User not found")
    return {"enabled": db_user.totp_enabled}

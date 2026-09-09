from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str, school_id: str | None, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {"sub": user_id, "school_id": school_id, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc


def create_2fa_challenge_token(user_id: str) -> str:
    """
    Issued right after a correct email/password when the account has 2FA
    enabled. Deliberately carries no school_id or role and expires in 5
    minutes — it can only be exchanged for a real access token by also
    providing a valid TOTP code (see /api/auth/2fa/verify-login), and
    decode_access_token would reject it anyway since it lacks the fields
    every real endpoint depends on.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    payload = {"sub": user_id, "purpose": "2fa_challenge", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_2fa_challenge_token(token: str) -> str:
    """Returns the user_id if valid, raises ValueError otherwise."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc

    if payload.get("purpose") != "2fa_challenge":
        raise ValueError("Not a valid 2FA challenge token")

    return payload["sub"]


def create_password_reset_token(user_id: str, password_hash: str) -> str:
    """Expires in 30 minutes. Carries a short fingerprint of the current
    password hash so that once someone actually resets their password, any
    older reset link they (or an attacker) still has stops working — the
    fingerprint in the old token no longer matches the new hash."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)
    payload = {
        "sub": user_id,
        "purpose": "password_reset",
        "pwd_fingerprint": password_hash[:12],
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_password_reset_token(token: str, current_password_hash: str) -> str:
    """Returns the user_id if valid and still fresh, raises ValueError otherwise."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc

    if payload.get("purpose") != "password_reset":
        raise ValueError("Not a valid password reset token")
    if payload.get("pwd_fingerprint") != current_password_hash[:12]:
        raise ValueError("This reset link has already been used")

    return payload["sub"]

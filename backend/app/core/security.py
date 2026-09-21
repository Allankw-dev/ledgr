from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except (ValueError, TypeError):
        # A malformed/unrecognised stored hash (bad import, manual edit) must
        # mean "wrong password" — not a 500 — and now that a phone number can
        # match several accounts, one bad record must not break the others.
        return False


def create_access_token(user_id: str, school_id: str | None, role: str, token_version: int = 0) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {"sub": user_id, "school_id": school_id, "role": role, "tv": token_version, "exp": expire}
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


def _email_fingerprint(email: str) -> str:
    import hashlib

    return hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]


def create_email_change_token(user_id: str, current_email: str, new_email: str) -> str:
    """Emailed to the NEW address; opening it proves the parent controls that
    inbox. Carries a fingerprint of the current email, so once the change is
    applied the same link (or any older one) is dead."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.email_change_expires_minutes)
    payload = {
        "sub": user_id,
        "purpose": "email_change",
        "new_email": new_email,
        "cur_fp": _email_fingerprint(current_email),
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_email_change_token(token: str) -> tuple[str, str, str]:
    """Returns (user_id, new_email, current_email_fingerprint) or raises ValueError."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired link") from exc
    if payload.get("purpose") != "email_change" or not payload.get("new_email"):
        raise ValueError("Not a valid email change link")
    return payload["sub"], payload["new_email"], payload["cur_fp"]

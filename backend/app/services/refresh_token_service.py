"""Rotating refresh tokens.

Access JWTs are short-lived and can't be revoked individually, so a refresh
token quietly mints new ones. Design:

  * Opaque random string, stored only as a SHA-256 hash.
  * Single use: each refresh rotates to a new token in the same family.
  * Reuse detection: a token that was already rotated, presented again after
    a short grace window, means a copy exists somewhere — the whole family is
    revoked and that sign-in must be redone. The grace window covers two
    browser tabs refreshing at the same moment with the same token.
  * Bound to users.token_version, so a password reset / email change kills
    every refresh token issued before it, and to users.is_active.
  * Hard absolute lifetime per family, so rotation can't extend a session forever.
"""

import hashlib
import random
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.refresh_token import RefreshToken
from app.models.school import User, gen_uuid


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _insert(db: Session, user: User, family_id: str, absolute_expires_at: datetime) -> str:
    now = _now()
    raw = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id,
            token_hash=_hash(raw),
            token_version=user.token_version or 0,
            expires_at=min(now + timedelta(days=settings.refresh_expires_days), absolute_expires_at),
            absolute_expires_at=absolute_expires_at,
        )
    )
    return raw


def issue_refresh_token(db: Session, user: User) -> str:
    """Start a new family (a fresh sign-in). Returns the raw token to hand to the client."""
    raw = _insert(db, user, gen_uuid(), _now() + timedelta(days=settings.refresh_absolute_days))
    db.commit()
    return raw


def _revoke_family(db: Session, family_id: str) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def rotate_refresh_token(db: Session, raw: str) -> tuple[User, str] | None:
    """Exchange a refresh token for a new one. Returns (user, new_raw_token),
    or None if the token is unknown, expired, revoked, reused, or its user is
    no longer allowed in."""
    row = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == _hash(raw)).with_for_update()
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return None

    now = _now()
    if _as_utc(row.expires_at) <= now or _as_utc(row.absolute_expires_at) <= now:
        return None

    user = db.get(User, row.user_id)
    if user is None or not user.is_active or row.token_version != (user.token_version or 0):
        _revoke_family(db, row.family_id)
        db.commit()
        return None

    if row.rotated_at is None:
        row.rotated_at = now
    elif now - _as_utc(row.rotated_at) > timedelta(seconds=settings.refresh_reuse_grace_seconds):
        # Already used, and not by a near-simultaneous twin request: treat as theft.
        _revoke_family(db, row.family_id)
        db.commit()
        return None
    # else: a concurrent refresh with the same token (two tabs) — issue a sibling.

    new_raw = _insert(db, user, row.family_id, _as_utc(row.absolute_expires_at))

    # Housekeeping: occasionally drop long-dead rows so the table stays small.
    if random.random() < 0.02:
        db.execute(delete(RefreshToken).where(RefreshToken.expires_at < now - timedelta(days=7)))

    db.commit()
    return user, new_raw


def revoke_token_family(db: Session, raw: str) -> None:
    """Sign-out: kill this device's whole family. Unknown tokens are ignored."""
    row = db.execute(select(RefreshToken).where(RefreshToken.token_hash == _hash(raw))).scalar_one_or_none()
    if row is not None:
        _revoke_family(db, row.family_id)
        db.commit()


def revoke_all_for_user(db: Session, user_id: str) -> None:
    """Sign a user out everywhere (password reset, email change). Caller commits."""
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )

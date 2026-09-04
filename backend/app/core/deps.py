from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token

bearer_scheme = HTTPBearer()


@dataclass
class CurrentUser:
    user_id: str
    school_id: str | None
    role: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    # A 2FA challenge token (see create_2fa_challenge_token) decodes fine
    # here since it's signed with the same secret, but deliberately carries
    # no "role" claim — reject it cleanly rather than crashing with a raw
    # KeyError, which would otherwise surface as an unhandled 500.
    role = payload.get("role")
    if not role:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    return CurrentUser(
        user_id=payload["sub"],
        school_id=payload.get("school_id"),
        role=role,
    )


def require_roles(*roles: str):
    """Usage: Depends(require_roles("SCHOOL_ADMIN", "BURSAR"))"""

    def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return checker


def get_school_scope(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> str:
    """
    Returns the schoolId every query in this request MUST be filtered by.
    This is the application-level choke point for tenant isolation: every
    router that touches school-owned data depends on this instead of trusting
    a schoolId that arrives in the request body or query params.

    It also mirrors that same schoolId into a Postgres session variable via
    set_config, so Row-Level Security policies (see sql/enable_rls.sql)
    enforce the identical restriction independently, at the database level.
    If this dependency ever had a bug, RLS still holds the line — that's the
    point of a second wall.

    Storing school_id on db.info (a plain dict attribute on the shared
    Session object) — not a ContextVar — matters: FastAPI dispatches each
    sync dependency and the sync route handler as separate calls to
    run_in_threadpool, each getting an independent copy of any ContextVar,
    so a value set here would be invisible by the time the route handler
    runs. db.info has no such problem, since `db` is the same shared Session
    object throughout the request regardless of which thread touches it —
    the after_begin listener in database.py reads it from there to
    re-apply the tenant context on every subsequent transaction too.
    """
    if user.role == "SUPER_ADMIN":
        # platform admin — callers must pass schoolId explicitly per-request
        # in routes that need it; this dependency just signals "unrestricted"
        # Note: RLS policies do not currently grant a bypass for this case —
        # see the "Known limitation" note in sql/enable_rls.sql.
        db.info.pop("school_id", None)
        return None  # type: ignore[return-value]

    if not user.school_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User is not attached to a school")

    db.info["school_id"] = user.school_id
    db.execute(
        text("SELECT set_config('app.current_school_id', :school_id, true)"),
        {"school_id": user.school_id},
    )

    return user.school_id


def get_db_session(db: Session = Depends(get_db)) -> Session:
    return db

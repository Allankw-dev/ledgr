"""A school's subscription: working out whether it is in good standing, and changing it.

The platform operator sets `subscription_status` (ACTIVE / TRIAL / SUSPENDED) and the dates; this module turns
those into what the school actually experiences:

    TRIAL / ACTIVE   in date
    GRACE            the date has passed, but there is a grace period before anything is switched off
    EXPIRED          grace is over -> Ledgr becomes READ-ONLY for the school's staff
    SUSPENDED        switched off by the operator -> read-only straight away

Read-only means staff can still look at everything but cannot change anything. Parents are NEVER affected:
they must keep being able to pay fees, and M-Pesa callbacks never go through this check at all.

A school that is ACTIVE with no `paid_until` never expires. That is what every existing school is migrated to.
"""

import calendar
import math
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import system_engine
from app.models.school import School
from app.models.student import Student
from app.services.audit_service import log_audit

GRACE_DAYS = 7
STATUSES = ("ACTIVE", "TRIAL", "SUSPENDED")

READ_ONLY_MESSAGE = (
    "This school's Ledgr subscription has ended, so Ledgr is read-only for now. "
    "Contact the Ledgr team to renew and carry on."
)


@dataclass(frozen=True)
class SubscriptionState:
    status: str  # TRIAL | ACTIVE | GRACE | EXPIRED | SUSPENDED
    read_only: bool
    # Whole days until the current period ends (TRIAL/ACTIVE), or until read-only starts (GRACE). None = no end date.
    days_left: int | None
    ends_at: datetime | None


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def compute_state(
    subscription_status: str,
    trial_ends_at: datetime | None,
    paid_until: datetime | None,
    now: datetime | None = None,
    grace_days: int = GRACE_DAYS,
) -> SubscriptionState:
    now = now or datetime.now(timezone.utc)

    if subscription_status == "SUSPENDED":
        return SubscriptionState("SUSPENDED", True, None, None)

    on_trial = subscription_status == "TRIAL"
    ends = _aware(trial_ends_at if on_trial else paid_until)
    in_date = "TRIAL" if on_trial else "ACTIVE"

    if ends is None:
        return SubscriptionState(in_date, False, None, None)

    if now <= ends:
        return SubscriptionState(in_date, False, math.ceil((ends - now).total_seconds() / 86400), ends)

    grace_ends = ends + timedelta(days=grace_days)
    if now <= grace_ends:
        return SubscriptionState("GRACE", False, math.ceil((grace_ends - now).total_seconds() / 86400), ends)

    return SubscriptionState("EXPIRED", True, 0, ends)


def add_months(dt: datetime, months: int) -> datetime:
    """Calendar months, clamped to the end of a shorter month (31 Jan + 1 month = 28/29 Feb)."""
    index = dt.month - 1 + months
    year, month = dt.year + index // 12, index % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


# --- a small per-worker cache, so enforcing this costs one tiny query per school per minute, not per request ---
_CACHE_SECONDS = max(15, settings.user_state_cache_seconds)
_school_state: dict[str, tuple[float, SubscriptionState]] = {}


def invalidate_school_state(school_id: str) -> None:
    _school_state.pop(school_id, None)


def get_school_state(school_id: str) -> SubscriptionState:
    now = time.monotonic()
    hit = _school_state.get(school_id)
    if hit and hit[0] > now:
        return hit[1]
    with system_engine.connect() as conn:
        row = conn.execute(
            text("SELECT subscription_status, trial_ends_at, paid_until FROM schools WHERE id = :id"), {"id": school_id}
        ).first()
    # An unknown school can't be judged here; the normal auth checks deal with it.
    state = compute_state(*row) if row else SubscriptionState("ACTIVE", False, None, None)
    if len(_school_state) > 5_000:
        _school_state.clear()
    _school_state[school_id] = (now + _CACHE_SECONDS, state)
    return state


def learner_count(db: Session, school_id: str) -> int:
    return db.scalar(select(func.count()).select_from(Student).where(Student.school_id == school_id, Student.is_active.is_(True))) or 0


LEARNER_LIMIT_MESSAGE = (
    "This school's plan allows up to {limit} active learners and {count} are already enrolled, so no more "
    "can be added. Contact the Ledgr team to raise the limit."
)


def enforce_learner_limit(db: Session, school_id: str, adding: int = 1) -> None:
    """Refuses to add `adding` more active learners if that would pass the school's `learner_limit`.
    No limit set (None) means no cap. Runs inside the caller's transaction and locks the school's row until
    it commits, so two bursars adding a student at the same moment can't both slip under the limit.

    A school already over its limit (the operator lowered it) keeps every learner it has; it just can't add
    more until it is back under."""
    limit = db.execute(
        select(School.learner_limit).where(School.id == school_id).with_for_update()
    ).scalar_one_or_none()
    if limit is None:
        return
    count = learner_count(db, school_id)
    if count + adding > limit:
        raise HTTPException(402, LEARNER_LIMIT_MESSAGE.format(limit=limit, count=count))


_UNSET = object()


def apply_update(
    db: Session,
    school: School,
    *,
    operator_id: str | None,
    status: str | None = None,
    plan: str | None = None,
    paid_until: datetime | None | object = _UNSET,
    trial_ends_at: datetime | None | object = _UNSET,
    learner_limit: int | None | object = _UNSET,
    extend_months: int | None = None,
    trial_days: int | None = None,
    now: datetime | None = None,
) -> School:
    """Changes a school's subscription and records who did it. `extend_months` is the everyday action
    ("they paid for another term"): it adds to whichever is later, today or the current paid-until date, so
    paying early never loses days, and it puts a suspended or expired school back to ACTIVE."""
    now = now or datetime.now(timezone.utc)
    before = {
        "status": school.subscription_status,
        "plan": school.plan,
        "paid_until": school.paid_until.isoformat() if school.paid_until else None,
        "trial_ends_at": school.trial_ends_at.isoformat() if school.trial_ends_at else None,
        "learner_limit": school.learner_limit,
    }

    if status is not None:
        school.subscription_status = status
    if plan is not None:
        school.plan = plan
    if paid_until is not _UNSET:
        school.paid_until = paid_until  # type: ignore[assignment]
    if trial_ends_at is not _UNSET:
        school.trial_ends_at = trial_ends_at  # type: ignore[assignment]
    if learner_limit is not _UNSET:
        school.learner_limit = learner_limit  # type: ignore[assignment]
    if trial_days is not None:
        school.subscription_status = "TRIAL"
        school.trial_ends_at = now + timedelta(days=trial_days)
    if extend_months is not None:
        base = max(now, _aware(school.paid_until) or now)
        school.paid_until = add_months(base, extend_months)
        school.subscription_status = "ACTIVE"

    log_audit(
        db,
        school_id=school.id,
        action="SUBSCRIPTION_UPDATED",
        entity_type="School",
        entity_id=school.id,
        user_id=operator_id,
        metadata={"before": before, "after": {
            "status": school.subscription_status,
            "plan": school.plan,
            "paid_until": school.paid_until.isoformat() if school.paid_until else None,
            "trial_ends_at": school.trial_ends_at.isoformat() if school.trial_ends_at else None,
            "learner_limit": school.learner_limit,
        }},
    )
    db.commit()
    db.refresh(school)
    invalidate_school_state(school.id)
    return school

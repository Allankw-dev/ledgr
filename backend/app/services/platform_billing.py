"""The operator's book of what schools pay for using Ledgr.

Recording a payment and extending the school's paid-until date happen in ONE transaction, so the money and the
date can't drift apart. The reference is unique per school (voided rows excluded), so a double click or the same
payment entered twice is refused rather than extending the subscription twice.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.school import School
from app.models.subscription_payment import SubscriptionPayment
from app.services.audit_service import log_audit
from app.services.subscription_service import apply_update


class DuplicateReference(Exception):
    """That reference is already booked for this school."""


class AlreadyVoided(Exception):
    pass


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def record_subscription_payment(
    db: Session,
    school: School,
    *,
    operator_id: str,
    amount: Decimal,
    method: str,
    reference: str | None,
    paid_on: datetime | None,
    months: int,
    note: str | None,
) -> SubscriptionPayment:
    reference = _clean(reference)
    row = SubscriptionPayment(
        school_id=school.id,
        amount=amount,
        currency=school.currency,
        method=method,
        reference=reference,
        paid_on=paid_on or datetime.now(timezone.utc),
        months_added=months,
        note=_clean(note),
        recorded_by_user_id=operator_id,
    )
    db.add(row)
    try:
        db.flush()  # the unique reference is checked here, BEFORE anything is extended
    except IntegrityError:
        db.rollback()
        raise DuplicateReference() from None
    log_audit(
        db,
        school_id=school.id,
        action="SUBSCRIPTION_PAYMENT_RECORDED",
        entity_type="SubscriptionPayment",
        entity_id=row.id,
        user_id=operator_id,
        metadata={"amount": str(amount), "currency": school.currency, "method": method, "reference": reference, "months": months},
    )
    if months:
        apply_update(db, school, operator_id=operator_id, extend_months=months)  # commits both together
    else:
        db.commit()
    db.refresh(row)
    return row


def void_subscription_payment(db: Session, row: SubscriptionPayment, *, operator_id: str, reason: str) -> SubscriptionPayment:
    if row.voided_at is not None:
        raise AlreadyVoided()
    row.voided_at = datetime.now(timezone.utc)
    row.voided_by_user_id = operator_id
    row.void_reason = reason.strip()
    log_audit(
        db,
        school_id=row.school_id,
        action="SUBSCRIPTION_PAYMENT_VOIDED",
        entity_type="SubscriptionPayment",
        entity_id=row.id,
        user_id=operator_id,
        metadata={"amount": str(row.amount), "reference": row.reference, "months_added": row.months_added},
    )
    db.commit()
    db.refresh(row)
    return row


def list_subscription_payments(db: Session, school_id: str, limit: int = 50) -> tuple[list[SubscriptionPayment], Decimal]:
    rows = (
        db.execute(
            select(SubscriptionPayment)
            .where(SubscriptionPayment.school_id == school_id)
            .order_by(SubscriptionPayment.paid_on.desc(), SubscriptionPayment.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    total = db.execute(
        select(func.coalesce(func.sum(SubscriptionPayment.amount), 0)).where(
            SubscriptionPayment.school_id == school_id, SubscriptionPayment.voided_at.is_(None)
        )
    ).scalar_one()
    return rows, Decimal(total)


def last_payment_by_school(db: Session) -> dict[str, datetime]:
    """Most recent non-voided payment date per school, for the operator's list (one query for all schools)."""
    return dict(
        db.execute(
            select(SubscriptionPayment.school_id, func.max(SubscriptionPayment.paid_on))
            .where(SubscriptionPayment.voided_at.is_(None))
            .group_by(SubscriptionPayment.school_id)
        ).all()
    )

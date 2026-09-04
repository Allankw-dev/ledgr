"""
Payment anomaly detection.

Same reasoning as risk_scoring.py and payment_plan_service.py: not enough
transaction volume yet for genuine statistical outlier detection to be
meaningful, so this flags payments against explainable, individually
defensible rules instead. Every flag comes with a plain-language reason —
a bursar reviewing these should always be able to see exactly why a
payment was surfaced, never just a bare "anomaly score."
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.enums import PaymentStatus


@dataclass
class PaymentAnomaly:
    payment_id: str
    student_id: str
    amount: Decimal
    paid_at: datetime | None
    reasons: list[str] = field(default_factory=list)

    @property
    def severity(self) -> str:
        if len(self.reasons) >= 2:
            return "high"
        return "medium"


def _check_unusually_large(db: Session, payment: Payment) -> str | None:
    """Flags a payment more than 3x this student's own typical payment
    size — compared against THEIR history, not a school-wide average,
    since normal fee sizes vary a lot by class/grade."""
    others = db.execute(
        select(Payment).where(
            Payment.student_id == payment.student_id,
            Payment.id != payment.id,
            Payment.status == PaymentStatus.CONFIRMED,
            Payment.amount > 0,
        )
    ).scalars().all()

    if len(others) < 2:
        return None  # not enough history to judge "unusual" against

    amounts = sorted(p.amount for p in others)
    mid = len(amounts) // 2
    median = amounts[mid] if len(amounts) % 2 else (amounts[mid - 1] + amounts[mid]) / 2

    if median > 0 and payment.amount > median * 3:
        return f"KES {payment.amount:,.0f} is over 3x this family's typical payment (median KES {median:,.0f})"
    return None


def _check_duplicate(db: Session, payment: Payment) -> str | None:
    """Same student, same exact amount, within 24 hours — classic sign of
    a double-submitted or accidentally re-entered payment."""
    if not payment.paid_at:
        return None

    window_start = payment.paid_at - timedelta(hours=24)
    window_end = payment.paid_at + timedelta(hours=24)

    duplicates = db.execute(
        select(Payment).where(
            Payment.student_id == payment.student_id,
            Payment.id != payment.id,
            Payment.amount == payment.amount,
            Payment.status == PaymentStatus.CONFIRMED,
            Payment.paid_at >= window_start,
            Payment.paid_at <= window_end,
        )
    ).scalars().all()

    if duplicates:
        return f"Another payment of the exact same amount (KES {payment.amount:,.0f}) was recorded for this student within 24 hours"
    return None


def _check_overpayment(db: Session, payment: Payment) -> str | None:
    """Flags when this payment pushed the invoice's total paid beyond what
    was actually owed."""
    if not payment.invoice_id:
        return None

    invoice = db.get(Invoice, payment.invoice_id)
    if not invoice:
        return None

    if invoice.amount_paid > invoice.total_amount:
        overage = invoice.amount_paid - invoice.total_amount
        return f"This invoice is now overpaid by KES {overage:,.0f} — total paid exceeds the amount owed"
    return None


def _check_repeated_failures(db: Session, payment: Payment) -> str | None:
    """3 or more failed/reversed attempts for this student in the last 7
    days — could be a struggling parent, a technical issue worth looking
    into, or in rare cases something worth a closer look either way."""
    window_start = datetime.now(timezone.utc) - timedelta(days=7)

    failures = db.execute(
        select(Payment).where(
            Payment.student_id == payment.student_id,
            Payment.status.in_([PaymentStatus.FAILED, PaymentStatus.REVERSED]),
            Payment.created_at >= window_start,
        )
    ).scalars().all()

    if len(failures) >= 3:
        return f"{len(failures)} failed or reversed payment attempts for this student in the last 7 days"
    return None


def check_payment(db: Session, payment: Payment) -> PaymentAnomaly:
    """Runs all checks against a single payment and returns the result
    regardless of whether anything was flagged — callers filter for
    non-empty `reasons` themselves."""
    reasons = []
    for check in (_check_unusually_large, _check_duplicate, _check_overpayment, _check_repeated_failures):
        result = check(db, payment)
        if result:
            reasons.append(result)

    return PaymentAnomaly(
        payment_id=payment.id,
        student_id=payment.student_id,
        amount=payment.amount,
        paid_at=payment.paid_at,
        reasons=reasons,
    )


def scan_recent_anomalies(db: Session, school_id: str, days: int = 30) -> list[PaymentAnomaly]:
    """Scans confirmed payments from the last `days` for this school and
    returns only the ones with at least one flag — this is what a bursar
    dashboard calls, not check_payment directly."""
    window_start = datetime.now(timezone.utc) - timedelta(days=days)

    payments = db.execute(
        select(Payment).where(
            Payment.school_id == school_id,
            Payment.status == PaymentStatus.CONFIRMED,
            Payment.amount > 0,
            Payment.created_at >= window_start,
        )
    ).scalars().all()

    flagged = []
    for payment in payments:
        result = check_payment(db, payment)
        if result.reasons:
            flagged.append(result)

    return flagged

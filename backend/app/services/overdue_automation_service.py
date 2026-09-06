"""Automated overdue-invoice escalation. A daily sweep (see main.py's
scheduler) walks every school that has opted in, finds overdue invoices due
for their next reminder tier, and sends it — the same email/SMS delivery
as a manually-triggered reminder, just decided by a schedule instead of a
bursar clicking a button.

Escalation is 3 tiers based on days overdue: a routine reminder at day 1,
a firmer follow-up at day 7, a final notice at day 14. Each invoice is
capped at tier 3 — this never re-sends the same tier twice, and it never
escalates further on its own; anything beyond a final notice is a human
decision, not an automated one.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import GuardianLinkStatus, InvoiceStatus
from app.models.invoice import Invoice, InvoiceReminderLog
from app.models.school import School, User
from app.models.student import Student, StudentGuardian
from app.services.notification_service import compose_overdue_escalation, send_message_to_guardian

# days-overdue required to reach each tier
TIER_THRESHOLDS: dict[int, int] = {1: 1, 2: 7, 3: 14}


def _tier_for_days_overdue(days_overdue: int) -> int | None:
    reached = None
    for tier, threshold in sorted(TIER_THRESHOLDS.items()):
        if days_overdue >= threshold:
            reached = tier
    return reached


@dataclass
class SweepResult:
    invoices_checked: int = 0
    reminders_sent: int = 0
    errors: list[str] = field(default_factory=list)


def run_overdue_reminder_sweep(db: Session, school_id: str) -> SweepResult:
    school = db.get(School, school_id)
    if not school:
        return SweepResult()

    now = datetime.now(timezone.utc)
    invoices = db.execute(
        select(Invoice).where(
            Invoice.school_id == school_id,
            Invoice.status == InvoiceStatus.OVERDUE,
            Invoice.total_amount > Invoice.amount_paid,
        )
    ).scalars().all()

    result = SweepResult(invoices_checked=len(invoices))

    for invoice in invoices:
        due_date = invoice.due_date
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)
        days_overdue = (now - due_date).days

        target_tier = _tier_for_days_overdue(days_overdue)
        if target_tier is None:
            continue

        last_tier_sent = db.execute(
            select(func.max(InvoiceReminderLog.tier)).where(InvoiceReminderLog.invoice_id == invoice.id)
        ).scalar()
        if last_tier_sent is not None and last_tier_sent >= target_tier:
            continue  # this tier (or a later one) already went out

        student = db.get(Student, invoice.student_id)
        if not student:
            continue

        links = db.execute(
            select(StudentGuardian).where(
                StudentGuardian.student_id == student.id,
                StudentGuardian.status == GuardianLinkStatus.APPROVED,
            )
        ).scalars().all()
        if not links:
            continue  # nothing to send to — not an error, just nothing to do yet

        balance = invoice.total_amount - invoice.amount_paid
        subject, body, sms_text = compose_overdue_escalation(
            target_tier, student.full_name, school.name, balance, school.currency, invoice.due_date
        )

        any_sent = False
        for link in links:
            guardian = db.get(User, link.user_id)
            if not guardian:
                continue
            outcome = send_message_to_guardian(guardian.email, guardian.phone, subject, body, sms_text)
            result.errors.extend(outcome.errors)
            if outcome.email_sent or outcome.sms_sent:
                any_sent = True

        if any_sent:
            db.add(InvoiceReminderLog(invoice_id=invoice.id, school_id=school_id, tier=target_tier))
            result.reminders_sent += 1

    db.commit()
    return result

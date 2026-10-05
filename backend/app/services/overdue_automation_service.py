"""Automated overdue-invoice escalation. A daily sweep (see main.py's
scheduler) walks every school that has opted in, finds overdue invoices due
for their next reminder tier, and QUEUES the reminder for each guardian — the
same email/SMS as a manually-triggered reminder, just decided by a schedule
instead of a bursar clicking a button.

The sweep itself never talks to an SMS/email provider. It decides who is due a
reminder, and writes the reminder log row and the delivery jobs in one transaction;
the job worker (core/jobs.py) does the slow part — concurrently, with retries. This
used to send every message inline, one at a time, inside the sweep: for a school with a
few thousand overdue invoices that was tens of minutes holding a database connection,
and the "run now" button's request would time out long before it finished.

Escalation is 3 tiers based on days overdue: a routine reminder at day 1,
a firmer follow-up at day 7, a final notice at day 14. Each invoice is
capped at tier 3 — this never re-sends the same tier twice, and it never
escalates further on its own; anything beyond a final notice is a human
decision, not an automated one.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.locks import try_advisory_lock
from app.models.enums import GuardianLinkStatus, InvoiceStatus
from app.models.invoice import Invoice, InvoiceReminderLog
from app.models.school import School, User
from app.models.student import Student, StudentGuardian
from app.core.jobs import enqueue_many
from app.services.job_handlers import guardian_message_jobs
from app.services.notification_service import compose_overdue_escalation

# days-overdue required to reach each tier
TIER_THRESHOLDS: dict[int, int] = {1: 1, 2: 7, 3: 14}

CHUNK = 200  # invoices per transaction: a crash loses at most one chunk, and the next run redoes only that


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
    """Only one sweep per school runs at a time, across ALL workers and
    instances (Postgres advisory lock) — a bursar clicking "run now" while
    the daily job fires, or several workers each running the scheduler, can
    no longer both send the same reminder. If another sweep holds the lock,
    this one returns immediately with a note instead of duplicating work."""
    with try_advisory_lock(f"overdue-sweep:{school_id}") as got_lock:
        if not got_lock:
            result = SweepResult()
            result.errors.append("A reminder sweep is already running for this school — skipped.")
            return result
        return _run_overdue_reminder_sweep_locked(db, school_id)


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _run_overdue_reminder_sweep_locked(db: Session, school_id: str) -> SweepResult:
    school = db.get(School, school_id)
    if not school:
        return SweepResult()

    # Read these once: db.commit() inside the loop expires every ORM object,
    # and re-fetching the school row for each invoice would be wasted queries.
    school_name, school_currency = school.name, school.currency

    now = datetime.now(timezone.utc)
    invoices = db.execute(
        select(Invoice).where(
            Invoice.school_id == school_id,
            Invoice.status == InvoiceStatus.OVERDUE,
            Invoice.total_amount > Invoice.amount_paid,
        )
    ).scalars().all()

    result = SweepResult(invoices_checked=len(invoices))

    # Which tier is each invoice due for, and has that tier (or a later one) already gone out?
    # One query for all invoices' history instead of one per invoice.
    last_tier_sent: dict[str, int] = {}
    for ids in _chunks([inv.id for inv in invoices], 2000):
        last_tier_sent.update(
            dict(
                db.execute(
                    select(InvoiceReminderLog.invoice_id, func.max(InvoiceReminderLog.tier))
                    .where(InvoiceReminderLog.invoice_id.in_(ids))
                    .group_by(InvoiceReminderLog.invoice_id)
                ).all()
            )
        )

    # Plain tuples, not ORM objects: db.commit() (once per chunk, below) expires every loaded object,
    # and touching an expired one quietly re-queries it — one extra round trip per invoice.
    due: list[tuple[str, str, Decimal, datetime, int]] = []  # (invoice_id, student_id, balance, due_date, tier)
    for invoice in invoices:
        due_date = invoice.due_date
        aware_due = due_date if due_date.tzinfo else due_date.replace(tzinfo=timezone.utc)
        target_tier = _tier_for_days_overdue((now - aware_due).days)
        if target_tier is None:
            continue
        sent = last_tier_sent.get(invoice.id)
        if sent is not None and sent >= target_tier:
            continue  # this tier (or a later one) already went out
        due.append((invoice.id, invoice.student_id, invoice.total_amount - invoice.amount_paid, due_date, target_tier))

    if not due:
        return result

    # Everything the messages need, loaded in bulk (students, their approved guardians, the guardians).
    student_ids = list({row[1] for row in due})
    student_names: dict[str, str] = {}
    guardian_ids_by_student: dict[str, list[str]] = {}
    for ids in _chunks(student_ids, 2000):
        student_names.update(dict(db.execute(select(Student.id, Student.full_name).where(Student.id.in_(ids))).all()))
        for student_id, user_id in db.execute(
            select(StudentGuardian.student_id, StudentGuardian.user_id).where(
                StudentGuardian.student_id.in_(ids), StudentGuardian.status == GuardianLinkStatus.APPROVED
            )
        ).all():
            guardian_ids_by_student.setdefault(student_id, []).append(user_id)
    all_guardian_ids = list({g for gs in guardian_ids_by_student.values() for g in gs})
    existing_guardians: set[str] = set()
    for ids in _chunks(all_guardian_ids, 2000):
        existing_guardians.update(db.execute(select(User.id).where(User.id.in_(ids))).scalars().all())

    for batch in _chunks(due, CHUNK):
        job_rows: list[dict] = []
        tier_by_invoice: dict[str, int] = {}
        prefix_by_invoice: dict[str, str] = {}
        for invoice_id, student_id, balance, due_date, target_tier in batch:
            student_name = student_names.get(student_id)
            if student_name is None:
                continue
            guardian_ids = [g for g in guardian_ids_by_student.get(student_id, []) if g in existing_guardians]
            if not guardian_ids:
                continue  # nothing to send to — not an error, just nothing to do yet

            subject, body, sms_text = compose_overdue_escalation(
                target_tier, student_name, school_name, balance, school_currency, due_date
            )
            prefix = f"overdue:{invoice_id}:t{target_tier}"
            tier_by_invoice[invoice_id] = target_tier
            prefix_by_invoice[invoice_id] = prefix
            for guardian_id in guardian_ids:
                job_rows.extend(
                    guardian_message_jobs(
                        school_id=school_id,
                        guardian_id=guardian_id,
                        email_subject=subject,
                        email_body=body,
                        sms_text=sms_text,
                        dedupe_prefix=prefix,
                    )
                )

        # One statement for the whole chunk's jobs; it reports which were genuinely new.
        inserted = enqueue_many(db, job_rows)
        for invoice_id, prefix in prefix_by_invoice.items():
            if any(key.startswith(prefix + ":") for key in inserted):
                db.add(InvoiceReminderLog(invoice_id=invoice_id, school_id=school_id, tier=tier_by_invoice[invoice_id]))
                result.reminders_sent += 1
        # The log rows and the jobs they correspond to commit together, a chunk at a time: if the
        # process dies, either a reminder is both logged and queued, or neither — never logged-but-lost.
        db.commit()

    return result

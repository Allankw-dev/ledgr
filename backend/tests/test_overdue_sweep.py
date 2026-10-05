"""The daily overdue sweep: who gets queued, never sent inline, never twice."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.enums import GuardianLinkStatus, InvoiceStatus, UserRole
from app.models.invoice import Invoice, InvoiceReminderLog
from app.models.job import Job
from app.models.school import User
from app.models.student import Student, StudentGuardian, Term
from app.services import notification_service
from app.services.overdue_automation_service import CHUNK, run_overdue_reminder_sweep
from tests.conftest import needs_db

pytestmark = needs_db


@pytest.fixture(autouse=True)
def _no_inline_sending(monkeypatch):
    """The sweep must never call a provider itself — only the job worker does."""
    def boom(*a, **k):
        raise AssertionError("the sweep sent a message inline")
    monkeypatch.setattr(notification_service, "send_email", boom)
    monkeypatch.setattr(notification_service, "send_sms", boom)
    monkeypatch.setattr(notification_service, "send_message_to_guardian", boom)


def _overdue(db, w, days, link=GuardianLinkStatus.APPROVED):
    w.invoice.status = InvoiceStatus.OVERDUE
    w.invoice.due_date = datetime.now(timezone.utc) - timedelta(days=days)
    if link:
        db.add(StudentGuardian(student_id=w.student.id, user_id=w.parent.id, relationship_type="mother", status=link))
    db.commit()


def _kinds(db):
    return sorted(j.kind for j in db.execute(select(Job)).scalars())


def test_queues_email_and_sms_and_logs_the_tier(db, world):
    _overdue(db, world, days=2)
    result = run_overdue_reminder_sweep(db, world.school.id)
    assert (result.invoices_checked, result.reminders_sent, result.errors) == (1, 1, [])
    assert _kinds(db) == ["send_email", "send_sms"]
    assert db.execute(select(InvoiceReminderLog.tier)).scalar_one() == 1
    body = db.execute(select(Job).where(Job.kind == "send_sms")).scalar_one().payload["text"]
    assert "Kid One" in body or "Test Academy" in body


def test_running_again_does_not_message_twice(db, world):
    _overdue(db, world, days=2)
    run_overdue_reminder_sweep(db, world.school.id)
    again = run_overdue_reminder_sweep(db, world.school.id)
    assert again.reminders_sent == 0
    assert len(_kinds(db)) == 2 and db.execute(select(func.count()).select_from(InvoiceReminderLog)).scalar_one() == 1


def test_escalates_tier_as_days_pass_but_never_repeats_a_tier(db, world):
    _overdue(db, world, days=2)
    run_overdue_reminder_sweep(db, world.school.id)  # tier 1
    world.invoice.due_date = datetime.now(timezone.utc) - timedelta(days=8)
    db.commit()
    assert run_overdue_reminder_sweep(db, world.school.id).reminders_sent == 1  # tier 2
    world.invoice.due_date = datetime.now(timezone.utc) - timedelta(days=30)
    db.commit()
    assert run_overdue_reminder_sweep(db, world.school.id).reminders_sent == 1  # tier 3
    assert run_overdue_reminder_sweep(db, world.school.id).reminders_sent == 0  # capped at tier 3
    assert sorted(db.execute(select(InvoiceReminderLog.tier)).scalars()) == [1, 2, 3]


def test_not_overdue_long_enough_is_left_alone(db, world):
    _overdue(db, world, days=0)  # due today: the first tier needs 1 day
    assert run_overdue_reminder_sweep(db, world.school.id).reminders_sent == 0
    assert _kinds(db) == []


def test_invoice_with_no_guardian_is_skipped_quietly(db, world):
    _overdue(db, world, days=5, link=None)
    result = run_overdue_reminder_sweep(db, world.school.id)
    assert (result.invoices_checked, result.reminders_sent, result.errors) == (1, 0, [])
    assert _kinds(db) == [] and db.execute(select(func.count()).select_from(InvoiceReminderLog)).scalar_one() == 0


def test_paid_invoices_are_not_chased(db, world):
    _overdue(db, world, days=5)
    world.invoice.amount_paid = world.invoice.total_amount
    db.commit()
    assert run_overdue_reminder_sweep(db, world.school.id).invoices_checked == 0


@pytest.mark.parametrize("status", [GuardianLinkStatus.PENDING, GuardianLinkStatus.REJECTED])
def test_unapproved_guardians_are_never_messaged(db, world, status):
    _overdue(db, world, days=5, link=status)
    assert run_overdue_reminder_sweep(db, world.school.id).reminders_sent == 0
    assert _kinds(db) == []


def test_every_approved_guardian_is_queued(db, world):
    _overdue(db, world, days=5)
    dad = User(school_id=world.school.id, email="dad@test.example", password_hash="x", role=UserRole.PARENT, full_name="Dad")
    db.add(dad)
    db.flush()
    db.add(StudentGuardian(student_id=world.student.id, user_id=dad.id, relationship_type="father", status=GuardianLinkStatus.APPROVED))
    db.commit()
    run_overdue_reminder_sweep(db, world.school.id)
    assert _kinds(db) == ["send_email", "send_email", "send_sms", "send_sms"]
    assert db.execute(select(func.count()).select_from(InvoiceReminderLog)).scalar_one() == 1  # one log per invoice


def test_big_school_commits_in_chunks_and_queues_everyone(db, world):
    """CHUNK + a few invoices, each with its own student and parent."""
    n = CHUNK + 15
    term = db.execute(select(Term)).scalars().first()
    for i in range(n):
        parent = User(school_id=world.school.id, email=f"bp{i}@test.example", password_hash="x", role=UserRole.PARENT, full_name=f"P{i}")
        kid = Student(school_id=world.school.id, admission_number=f"b{i}", full_name=f"Kid {i}")
        db.add_all([parent, kid])
        db.flush()
        db.add(StudentGuardian(student_id=kid.id, user_id=parent.id, relationship_type="mother", status=GuardianLinkStatus.APPROVED))
        db.add(Invoice(school_id=world.school.id, student_id=kid.id, term_id=term.id, total_amount=Decimal("1000"),
                       due_date=datetime.now(timezone.utc) - timedelta(days=3), status=InvoiceStatus.OVERDUE))
    db.commit()
    result = run_overdue_reminder_sweep(db, world.school.id)
    assert result.invoices_checked == n and result.reminders_sent == n
    assert db.execute(select(func.count()).select_from(Job)).scalar_one() == 2 * n
    assert db.execute(select(func.count()).select_from(InvoiceReminderLog)).scalar_one() == n

"""Paying toward a student's WHOLE balance (the big 'Pay with M-Pesa' button),
as opposed to one invoice. The money is split across open invoices, oldest due
date first, when the M-Pesa callback arrives."""

import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.database import SystemSessionLocal
from app.core.deps import CurrentUser
from app.models.enums import GuardianLinkStatus, InvoiceStatus, PaymentMethod, PaymentStatus
from app.models.invoice import Invoice
from app.models.job import Job
from app.models.payment import AuditLog, Payment
from app.models.school import User
from app.models.student import StudentGuardian, Term
from app.routers.mpesa import _prepare_stk_push
from app.schemas.mpesa import StkPushRequest
from app.services import payment_service as ps
from tests.conftest import needs_db

D = Decimal


def test_request_needs_exactly_one_target():
    ok = StkPushRequest(student_id="s1", phone_number="0712345678")
    assert ok.invoice_id is None
    with pytest.raises(ValidationError):
        StkPushRequest(phone_number="0712345678")
    with pytest.raises(ValidationError):
        StkPushRequest(invoice_id="i1", student_id="s1", phone_number="0712345678")
    StkPushRequest(invoice_id="i1", phone_number="0712345678")  # the old per-invoice shape still works


def _add_invoice(db, w, name, total, due_in_days):
    term = Term(
        school_id=w.school.id, name=name, start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=90),
    )
    db.add(term)
    db.flush()
    inv = Invoice(
        school_id=w.school.id, student_id=w.student.id, term_id=term.id, total_amount=D(total),
        due_date=datetime.now(timezone.utc) + timedelta(days=due_in_days), status=InvoiceStatus.ISSUED,
    )
    db.add(inv)
    db.commit()
    return inv


@pytest.fixture()
def three(db, world):
    """Reproduces the reported account: a tiny KES 10 invoice due LATER than a
    big KES 56,010 one, plus the fixture's KES 10,000 invoice due in 30 days.
    Oldest due date first => 56,010 (due 5d), 10,000 (due 30d), 10 (due 90d)."""
    big = _add_invoice(db, world, "Term A", "56010", 5)
    tiny = _add_invoice(db, world, "Term B", "10", 90)
    return world.invoice, big, tiny  # (mid, oldest, newest)


def _link_parent(db, w):
    db.add(StudentGuardian(student_id=w.student.id, user_id=w.parent.id, relationship_type="mother",
                           status=GuardianLinkStatus.APPROVED))
    db.commit()


def _req(w, **kw):
    return StkPushRequest(student_id=w.student.id, phone_number="0712345678", **kw)


def _pending(db, w, amount, cid="ws_CO_whole"):
    return ps.create_pending_mpesa_payment(db, w.school.id, w.student.id, None, D(amount), cid)


def _invoice(db, inv):
    db.expire_all()
    return db.get(Invoice, inv.id)


# --- the STK push request -----------------------------------------------------


@needs_db
def test_balance_is_the_whole_account_not_the_first_invoice(db, world, three):
    _link_parent(db, world)
    user = CurrentUser(user_id=world.parent.id, school_id=world.school.id, role="PARENT")
    invoice, amount, student = _prepare_stk_push(db, _req(world), user, world.school.id)
    assert invoice is None and student.id == world.student.id
    assert amount == D("66020")  # 56,010 + 10,000 + 10 — NOT the 10 from the screenshot


@needs_db
def test_parent_can_pay_any_amount_up_to_the_whole_balance(db, world, three):
    _link_parent(db, world)
    user = CurrentUser(user_id=world.parent.id, school_id=world.school.id, role="PARENT")
    assert _prepare_stk_push(db, _req(world, amount=D("30000")), user, world.school.id)[1] == D("30000")
    assert _prepare_stk_push(db, _req(world, amount=D("66020")), user, world.school.id)[1] == D("66020")
    with pytest.raises(HTTPException) as e:
        _prepare_stk_push(db, _req(world, amount=D("66021")), user, world.school.id)
    assert e.value.status_code == 422


@needs_db
def test_parent_cannot_pay_for_a_child_that_is_not_theirs(db, world, three):
    stranger = User(school_id=world.school.id, email="x@test.example", password_hash="x",
                    role=world.parent.role, full_name="Stranger")
    db.add(stranger)
    db.commit()
    user = CurrentUser(user_id=stranger.id, school_id=world.school.id, role="PARENT")
    with pytest.raises(HTTPException) as e:
        _prepare_stk_push(db, _req(world), user, world.school.id)
    assert e.value.status_code == 403


@needs_db
def test_student_from_another_school_is_404(db, world, three):
    user = CurrentUser(user_id=world.bursar.id, school_id="other-school", role="BURSAR")
    with pytest.raises(HTTPException) as e:
        _prepare_stk_push(db, _req(world), user, "other-school")
    assert e.value.status_code == 404


@needs_db
def test_nothing_owed_is_rejected(db, world):
    ps.record_confirmed_payment(db, world.school.id, world.student.id, D("10000"), PaymentMethod.CASH, invoice_id=world.invoice.id)
    user = CurrentUser(user_id=world.bursar.id, school_id=world.school.id, role="BURSAR")
    with pytest.raises(HTTPException) as e:
        _prepare_stk_push(db, _req(world), user, world.school.id)
    assert e.value.status_code == 422


@needs_db
def test_cancelled_and_draft_invoices_are_not_collectable(db, world, three):
    _, big, tiny = three
    big.status = InvoiceStatus.CANCELLED
    tiny.status = InvoiceStatus.DRAFT
    db.commit()
    user = CurrentUser(user_id=world.bursar.id, school_id=world.school.id, role="BURSAR")
    assert _prepare_stk_push(db, _req(world), user, world.school.id)[1] == D("10000")


# --- the callback splits the money -------------------------------------------


@needs_db
def test_payment_clears_oldest_invoice_first_then_spills_over(db, world, three):
    mid, big, tiny = three
    _pending(db, world, "60000")
    first = ps.resolve_mpesa_callback(db, "ws_CO_whole", 0, "RCPSPLIT", paid_amount=60000)
    assert first is not None

    assert _invoice(db, big).amount_paid == D("56010.00") and _invoice(db, big).status == InvoiceStatus.PAID
    assert _invoice(db, mid).amount_paid == D("3990.00") and _invoice(db, mid).status == InvoiceStatus.PARTIALLY_PAID
    assert _invoice(db, tiny).amount_paid == 0 and _invoice(db, tiny).status == InvoiceStatus.ISSUED

    rows = db.execute(select(Payment).order_by(Payment.amount.desc())).scalars().all()
    assert [r.amount for r in rows] == [D("56010.00"), D("3990.00")]
    assert {r.reference_code for r in rows} == {"RCPSPLIT"}  # one M-Pesa receipt, shown on every slice
    assert all(r.status == PaymentStatus.CONFIRMED for r in rows)
    assert sum(r.amount for r in rows) == D("60000")  # not a shilling created or lost


@needs_db
def test_paying_the_exact_total_clears_everything(db, world, three):
    _pending(db, world, "66020")
    ps.resolve_mpesa_callback(db, "ws_CO_whole", 0, "RCPALL", paid_amount=66020)
    for inv in three:
        assert _invoice(db, inv).status == InvoiceStatus.PAID
    assert db.execute(select(func.count()).select_from(Payment)).scalar_one() == 3


@needs_db
def test_small_part_payment_only_touches_the_oldest_invoice(db, world, three):
    mid, big, tiny = three
    _pending(db, world, "1000")
    ps.resolve_mpesa_callback(db, "ws_CO_whole", 0, "RCPSMALL", paid_amount=1000)
    assert _invoice(db, big).amount_paid == D("1000.00")
    assert _invoice(db, mid).amount_paid == 0 and _invoice(db, tiny).amount_paid == 0
    assert db.execute(select(func.count()).select_from(Payment)).scalar_one() == 1


@needs_db
def test_one_notification_with_the_full_amount_and_overall_balance(db, world, three):
    _pending(db, world, "60000")
    ps.resolve_mpesa_callback(db, "ws_CO_whole", 0, "RCPSPLIT", paid_amount=60000)
    job = db.execute(select(Job).where(Job.kind == "notify_payment_result")).scalar_one()
    assert D(job.payload["amount"]) == D("60000")
    assert D(job.payload["remaining"]) == D("6020")  # 66,020 - 60,000, across ALL invoices


@needs_db
def test_amount_mismatch_still_refuses_to_confirm_a_whole_balance_payment(db, world, three):
    _pending(db, world, "5000")
    assert ps.resolve_mpesa_callback(db, "ws_CO_whole", 0, "RCP", paid_amount=4000) is None
    assert db.execute(select(func.sum(Payment.amount)).where(Payment.status == PaymentStatus.CONFIRMED)).scalar_one() is None


@needs_db
def test_cancelled_prompt_fails_cleanly_and_touches_no_invoice(db, world, three):
    _pending(db, world, "5000")
    p = ps.resolve_mpesa_callback(db, "ws_CO_whole", 1032, None)
    assert p.status == PaymentStatus.FAILED
    for inv in three:
        assert _invoice(db, inv).amount_paid == 0


@needs_db
def test_duplicate_callback_does_not_split_twice(db, world, three):
    _pending(db, world, "60000")
    assert ps.resolve_mpesa_callback(db, "ws_CO_whole", 0, "R", paid_amount=60000) is not None
    assert ps.resolve_mpesa_callback(db, "ws_CO_whole", 0, "R", paid_amount=60000) is None
    assert db.execute(select(func.sum(Payment.amount))).scalar_one() == D("60000.00")
    assert db.execute(select(func.count()).select_from(Job)).scalar_one() == 1


@needs_db
def test_invoice_paid_off_in_the_meantime_is_not_overpaid(db, world, three):
    """Parent starts a 66,020 prompt; before they enter their PIN the bursar records
    the 56,010 invoice as cash. The callback must not push that invoice past 100%."""
    mid, big, tiny = three
    _pending(db, world, "66020")
    ps.record_confirmed_payment(db, world.school.id, world.student.id, D("56010"), PaymentMethod.CASH, invoice_id=big.id)
    ps.resolve_mpesa_callback(db, "ws_CO_whole", 0, "RCPLATE", paid_amount=66020)

    assert _invoice(db, big).amount_paid == D("56010.00")  # not 112,020
    assert _invoice(db, mid).status == InvoiceStatus.PAID and _invoice(db, tiny).status == InvoiceStatus.PAID
    leftover = db.execute(select(Payment).where(Payment.invoice_id.is_(None))).scalar_one()
    assert leftover.amount == D("56010.00") and leftover.status == PaymentStatus.CONFIRMED
    actions = [a.action for a in db.execute(select(AuditLog)).scalars()]
    assert "MPESA_PAYMENT_UNALLOCATED" in actions  # a human is told about the 56,010 with no invoice


@needs_db
def test_everything_already_paid_keeps_the_money_unallocated_and_flagged(db, world):
    _pending(db, world, "500")
    ps.record_confirmed_payment(db, world.school.id, world.student.id, D("10000"), PaymentMethod.CASH, invoice_id=world.invoice.id)
    ps.resolve_mpesa_callback(db, "ws_CO_whole", 0, "RCPNONE", paid_amount=500)
    row = db.execute(select(Payment).where(Payment.reference_code == "RCPNONE")).scalar_one()
    assert row.invoice_id is None and row.amount == D("500.00") and row.status == PaymentStatus.CONFIRMED
    assert "MPESA_PAYMENT_UNALLOCATED" in [a.action for a in db.execute(select(AuditLog)).scalars()]


@needs_db
def test_split_payment_can_be_reversed_slice_by_slice(db, world, three):
    mid, big, tiny = three
    _pending(db, world, "60000")
    ps.resolve_mpesa_callback(db, "ws_CO_whole", 0, "RCPSPLIT", paid_amount=60000)
    big_slice = db.execute(select(Payment).where(Payment.invoice_id == big.id)).scalar_one()
    ps.reverse_payment(db, world.school.id, big_slice.id, "wrong phone")
    assert _invoice(db, big).amount_paid == 0
    assert _invoice(db, mid).amount_paid == D("3990.00")  # the other slice is untouched


@needs_db
def test_concurrent_cash_payment_and_duplicate_callbacks_stay_consistent(db, world, three):
    """Cash on the big invoice racing two copies of the same M-Pesa callback: no
    deadlock, the callback confirms exactly once, and no money is created or lost.
    (A cash entry made AFTER the callback can legitimately exceed an invoice — manual
    cash entry has never been capped — so overpayment isn't asserted here; the
    deterministic 'paid in the meantime' case above covers the callback's own rule.)"""
    mid, big, tiny = three
    _pending(db, world, "66020")
    errors, results = [], []

    def cash():
        try:
            with SystemSessionLocal() as s:
                ps.record_confirmed_payment(s, world.school.id, world.student.id, D("56010"), PaymentMethod.CASH, invoice_id=big.id)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def callback():
        try:
            with SystemSessionLocal() as s:
                results.append(ps.resolve_mpesa_callback(s, "ws_CO_whole", 0, "RCPRACE", paid_amount=66020))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=f) for f in (cash, callback, callback)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert sum(r is not None for r in results) == 1
    db.expire_all()
    confirmed = db.execute(select(func.sum(Payment.amount)).where(Payment.status == PaymentStatus.CONFIRMED)).scalar_one()
    assert confirmed == D("66020") + D("56010")  # every shilling accounted for, none duplicated
    for inv in (mid, big, tiny):
        fresh = db.get(Invoice, inv.id)
        ledger = db.execute(select(func.sum(Payment.amount)).where(Payment.invoice_id == inv.id)).scalar_one() or 0
        assert fresh.amount_paid == ledger  # stored balance always equals its payment rows

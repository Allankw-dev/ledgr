import threading
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.database import SystemSessionLocal
from app.models.enums import InvoiceStatus, PaymentMethod, PaymentStatus
from app.models.invoice import Invoice
from app.models.job import Job
from app.models.payment import AuditLog, Payment
from app.services import payment_service as ps
from tests.conftest import needs_db

pytestmark = needs_db

D = Decimal


def _invoice(db, w):
    db.expire_all()
    return db.get(Invoice, w.invoice.id)


def _pay(db, w, amount, **kw):
    return ps.record_confirmed_payment(
        db, w.school.id, w.student.id, D(amount), PaymentMethod.CASH, invoice_id=w.invoice.id, **kw
    )


def test_part_payments_move_invoice_through_statuses(db, world):
    _pay(db, world, "2500")
    inv = _invoice(db, world)
    assert inv.amount_paid == D("2500.00") and inv.status == InvoiceStatus.PARTIALLY_PAID
    _pay(db, world, "7500")
    inv = _invoice(db, world)
    assert inv.amount_paid == D("10000.00") and inv.status == InvoiceStatus.PAID


def test_non_positive_amount_rejected(db, world):
    for bad in ("0", "-5"):
        with pytest.raises(HTTPException) as e:
            _pay(db, world, bad)
        assert e.value.status_code == 422


def test_payment_writes_audit_row_and_one_notification_job(db, world):
    p = _pay(db, world, "1000")
    audit = db.execute(select(AuditLog).where(AuditLog.entity_id == p.id)).scalars().all()
    assert [a.action for a in audit] == ["PAYMENT_CONFIRMED"]
    jobs = db.execute(select(Job).where(Job.kind == "notify_payment_result")).scalars().all()
    assert len(jobs) == 1 and jobs[0].payload == {"payment_id": p.id, "succeeded": True}


def test_notification_enqueue_is_deduplicated(db, world):
    p = _pay(db, world, "1000")
    ps.queue_payment_notification(db, p, succeeded=True)  # e.g. a duplicate callback
    db.commit()
    assert db.execute(select(func.count()).select_from(Job)).scalar_one() == 1


def test_rolled_back_payment_leaves_no_job_behind(db, world):
    """Transactional outbox: no commit, no notification."""
    _pay(db, world, "1000", commit=False)
    db.rollback()
    assert db.execute(select(func.count()).select_from(Job)).scalar_one() == 0
    assert db.execute(select(func.count()).select_from(Payment)).scalar_one() == 0


def test_pending_payment_not_counted_until_confirmed(db, world):
    ps.create_pending_mpesa_payment(db, world.school.id, world.student.id, world.invoice.id, D("3000"), "ws_CO_1")
    assert _invoice(db, world).amount_paid == 0


# --- M-Pesa callback ----------------------------------------------------------


def _pending(db, w, amount="3000", cid="ws_CO_1"):
    return ps.create_pending_mpesa_payment(db, w.school.id, w.student.id, w.invoice.id, D(amount), cid)


def test_callback_success_confirms_and_updates_invoice(db, world):
    _pending(db, world)
    p = ps.resolve_mpesa_callback(db, "ws_CO_1", 0, "RCP123", paid_amount=3000)
    assert p.status == PaymentStatus.CONFIRMED and p.reference_code == "RCP123"
    inv = _invoice(db, world)
    assert inv.amount_paid == D("3000.00") and inv.status == InvoiceStatus.PARTIALLY_PAID


def test_duplicate_callback_is_a_noop(db, world):
    _pending(db, world)
    assert ps.resolve_mpesa_callback(db, "ws_CO_1", 0, "RCP123", paid_amount=3000) is not None
    assert ps.resolve_mpesa_callback(db, "ws_CO_1", 0, "RCP123", paid_amount=3000) is None
    assert _invoice(db, world).amount_paid == D("3000.00")  # not 6000
    assert db.execute(select(func.count()).select_from(Job)).scalar_one() == 1


def test_callback_amount_mismatch_leaves_payment_pending_and_flags_it(db, world):
    _pending(db, world, amount="3000")
    assert ps.resolve_mpesa_callback(db, "ws_CO_1", 0, "RCP123", paid_amount=2999) is None
    pay = db.execute(select(Payment)).scalar_one()
    assert pay.status == PaymentStatus.PENDING
    assert _invoice(db, world).amount_paid == 0
    actions = [a.action for a in db.execute(select(AuditLog)).scalars()]
    assert "MPESA_CALLBACK_AMOUNT_MISMATCH" in actions


def test_callback_failure_marks_failed_and_does_not_touch_invoice(db, world):
    _pending(db, world)
    p = ps.resolve_mpesa_callback(db, "ws_CO_1", 1032, None)  # 1032 = cancelled by user
    assert p.status == PaymentStatus.FAILED
    assert _invoice(db, world).amount_paid == 0
    job = db.execute(select(Job)).scalar_one()
    assert job.payload["succeeded"] is False


def test_callback_for_unknown_checkout_id_is_noop(db, world):
    assert ps.resolve_mpesa_callback(db, "ws_CO_nope", 0, "X", paid_amount=1) is None


# --- reversal -----------------------------------------------------------------


def test_reversal_restores_invoice_and_is_append_only(db, world):
    p = _pay(db, world, "10000")
    assert _invoice(db, world).status == InvoiceStatus.PAID
    rev = ps.reverse_payment(db, world.school.id, p.id, "entered twice", actor_user_id=world.bursar.id)
    assert rev.amount == D("-10000.00") and rev.reversal_of_id == p.id
    inv = _invoice(db, world)
    assert inv.amount_paid == 0 and inv.status in (InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE)
    db.expire_all()
    assert db.get(Payment, p.id).status == PaymentStatus.REVERSED
    assert db.execute(select(func.count()).select_from(Payment)).scalar_one() == 2  # original kept + reversal row


def test_cannot_reverse_twice(db, world):
    p = _pay(db, world, "1000")
    ps.reverse_payment(db, world.school.id, p.id, "oops")
    with pytest.raises(HTTPException) as e:
        ps.reverse_payment(db, world.school.id, p.id, "oops again")
    assert e.value.status_code == 422


# --- real concurrency (separate sessions, separate connections) ----------------


def _run_threads(target, n):
    errors = []

    def wrap(i):
        try:
            target(i)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=wrap, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return errors


def test_concurrent_payments_on_one_invoice_all_counted(db, world):
    school_id, student_id, invoice_id = world.school.id, world.student.id, world.invoice.id
    n = 8

    def work(_):
        with SystemSessionLocal() as s:
            ps.record_confirmed_payment(s, school_id, student_id, D("1000"), PaymentMethod.CASH, invoice_id=invoice_id)

    assert _run_threads(work, n) == []
    db.expire_all()
    inv = db.get(Invoice, invoice_id)
    assert inv.amount_paid == D("8000.00")  # no lost update
    assert inv.status == InvoiceStatus.PARTIALLY_PAID


def test_concurrent_duplicate_callbacks_confirm_exactly_once(db, world):
    _pending(db, world, amount="4000", cid="ws_CO_race")

    results = []

    def work(_):
        with SystemSessionLocal() as s:
            results.append(ps.resolve_mpesa_callback(s, "ws_CO_race", 0, "RCPRACE", paid_amount=4000))

    assert _run_threads(work, 5) == []
    assert sum(r is not None for r in results) == 1
    db.expire_all()
    assert db.get(Invoice, world.invoice.id).amount_paid == D("4000.00")
    assert db.execute(select(func.count()).select_from(Job)).scalar_one() == 1


def test_concurrent_reversal_only_one_wins(db, world):
    p = _pay(db, world, "5000")
    pid = p.id
    outcomes = []

    def work(_):
        with SystemSessionLocal() as s:
            try:
                ps.reverse_payment(s, world.school.id, pid, "double click")
                outcomes.append("ok")
            except HTTPException as exc:
                outcomes.append(exc.status_code)

    assert _run_threads(work, 4) == []
    assert outcomes.count("ok") == 1 and outcomes.count(422) == 3
    db.expire_all()
    assert db.get(Invoice, world.invoice.id).amount_paid == 0

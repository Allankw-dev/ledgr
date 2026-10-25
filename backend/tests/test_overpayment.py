"""Money that comes to more than an invoice owes must never be recorded as an overpayment (paid > total).

It used to be: two payments for the same invoice both confirmed, and a KES 10,000 invoice showed 20,000 paid.
Now the invoice takes what it owes and the rest is held as unallocated credit, which the bursar can see and apply.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app.core.security import create_access_token
from app.main import app
from app.models.enums import GuardianLinkStatus, InvoiceStatus, PaymentMethod, PaymentStatus
from app.models.invoice import Invoice
from app.models.payment import AuditLog, Payment
from app.models.student import StudentGuardian
from app.services import payment_service as ps
from tests.conftest import needs_db

pytestmark = needs_db
D = Decimal


def _invoice(db, w):
    db.expire_all()
    return db.get(Invoice, w.invoice.id)


def _held(db, w):
    return db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.student_id == w.student.id, Payment.invoice_id.is_(None), Payment.status == PaymentStatus.CONFIRMED
        )
    )


# ---- at confirmation -------------------------------------------------------------------------


def test_two_full_mpesa_payments_on_one_invoice_pay_it_once_and_hold_the_rest(db, world):
    total = world.invoice.total_amount
    for n in ("ws_A", "ws_B"):
        ps.create_pending_mpesa_payment(db, world.school.id, world.student.id, world.invoice.id, D(total), n)
    ps.resolve_mpesa_callback(db, "ws_A", 0, "RCPTA", total)
    ps.resolve_mpesa_callback(db, "ws_B", 0, "RCPTB", total)

    inv = _invoice(db, world)
    assert inv.amount_paid == inv.total_amount and inv.status == InvoiceStatus.PAID
    assert _held(db, world) == D(total)  # the second payment is real money, kept safe as credit
    row = db.execute(select(Payment).where(Payment.reference_code == "RCPTB")).scalar_one()
    assert row.invoice_id is None and "more than the invoice still owed" in (row.notes or "")


def test_a_payment_that_is_part_over_is_split_and_the_parent_is_told_the_full_amount(db, world):
    db.execute(update(Invoice).where(Invoice.id == world.invoice.id).values(total_amount=D("1000"), amount_paid=D("0")))
    db.commit()
    ps.create_pending_mpesa_payment(db, world.school.id, world.student.id, world.invoice.id, D("1300"), "ws_C")
    ps.resolve_mpesa_callback(db, "ws_C", 0, "RCPTC", 1300)

    assert _invoice(db, world).amount_paid == D("1000")
    assert _held(db, world) == D("300")
    assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "MPESA_PAYMENT_EXCESS_HELD")) == 1


def test_a_normal_exact_payment_is_untouched(db, world):
    total = world.invoice.total_amount
    ps.create_pending_mpesa_payment(db, world.school.id, world.student.id, world.invoice.id, D(total), "ws_D")
    ps.resolve_mpesa_callback(db, "ws_D", 0, "RCPTD", total)
    assert _invoice(db, world).amount_paid == total
    assert _held(db, world) == 0
    assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "MPESA_PAYMENT_EXCESS_HELD")) == 0


def test_a_bursar_recording_more_than_is_owed_cannot_overpay_the_invoice_either(db, world):
    ps.record_confirmed_payment(db, world.school.id, world.student.id, D(world.invoice.total_amount) + D("2500"), PaymentMethod.CASH, invoice_id=world.invoice.id)
    inv = _invoice(db, world)
    assert inv.amount_paid == inv.total_amount and inv.status == InvoiceStatus.PAID
    assert _held(db, world) == D("2500")


def test_paying_an_already_paid_invoice_holds_the_whole_amount(db, world):
    ps.record_confirmed_payment(db, world.school.id, world.student.id, D(world.invoice.total_amount), PaymentMethod.CASH, invoice_id=world.invoice.id)
    ps.record_confirmed_payment(db, world.school.id, world.student.id, D("700"), PaymentMethod.CASH, invoice_id=world.invoice.id)
    assert _invoice(db, world).amount_paid == _invoice(db, world).total_amount
    assert _held(db, world) == D("700")


def test_held_credit_shows_up_for_the_bursar_to_apply(db, world):
    ps.record_confirmed_payment(db, world.school.id, world.student.id, D(world.invoice.total_amount) + D("900"), PaymentMethod.CASH, invoice_id=world.invoice.id)
    [row] = ps.list_unallocated_payments(db, world.school.id)
    assert row["amount"] == D("900.00") and row["student_name"] == "Kid One"


# ---- not asking twice -----------------------------------------------------------------------


def test_a_second_prompt_is_refused_while_the_first_is_still_waiting(db, world):
    ps.create_pending_mpesa_payment(db, world.school.id, world.student.id, world.invoice.id, D(world.invoice.total_amount), "ws_E")
    assert ps.pending_mpesa_total(db, world.student.id, world.invoice.id) == D(world.invoice.total_amount)


def test_an_old_unanswered_prompt_stops_counting(db, world):
    pay = ps.create_pending_mpesa_payment(db, world.school.id, world.student.id, world.invoice.id, D("500"), "ws_F")
    db.execute(update(Payment).where(Payment.id == pay.id).values(created_at=datetime.now(timezone.utc) - timedelta(minutes=10)))
    db.commit()
    assert ps.pending_mpesa_total(db, world.student.id, world.invoice.id) == 0


def test_a_failed_prompt_does_not_count(db, world):
    ps.create_pending_mpesa_payment(db, world.school.id, world.student.id, world.invoice.id, D("500"), "ws_G")
    ps.resolve_mpesa_callback(db, "ws_G", 1032, None)  # cancelled on the phone
    assert ps.pending_mpesa_total(db, world.student.id, world.invoice.id) == 0


def test_whole_balance_prompts_count_against_an_invoice_but_other_invoices_prompts_dont(db, world):
    ps.create_pending_mpesa_payment(db, world.school.id, world.student.id, None, D("400"), "ws_H")
    assert ps.pending_mpesa_total(db, world.student.id, world.invoice.id) == D("400")
    assert ps.pending_mpesa_total(db, world.student.id, None) == D("400")


@pytest.fixture()
def parent_client(db, world):
    from app.core.rate_limit import limiter

    limiter.reset()
    c = TestClient(app)
    c.headers["Authorization"] = "Bearer " + create_access_token(world.parent.id, world.school.id, "PARENT")
    yield c
    limiter.reset()


def test_http_second_stk_push_gets_a_clear_409_not_a_second_prompt(db, world, parent_client, monkeypatch):
    from app.core.config import settings
    from app.routers import mpesa as mpesa_router

    if db.execute(select(StudentGuardian).where(StudentGuardian.user_id == world.parent.id)).scalar_one_or_none() is None:
        db.add(StudentGuardian(student_id=world.student.id, user_id=world.parent.id, relationship_type="mother", status=GuardianLinkStatus.APPROVED))
        db.commit()
    monkeypatch.setattr(settings, "mpesa_callback_url", "https://example.test/cb")
    sent = []

    async def fake_push(**kw):
        sent.append(kw)
        return {"CheckoutRequestID": f"ws_CO_{len(sent)}", "MerchantRequestID": "m", "CustomerMessage": "ok"}

    monkeypatch.setattr(mpesa_router, "initiate_stk_push", fake_push)
    body = {"invoice_id": world.invoice.id, "phone_number": "0712345678"}
    first = parent_client.post("/api/payments/mpesa/stk-push", json=body)
    second = parent_client.post("/api/payments/mpesa/stk-push", json=body)
    assert first.status_code == 201
    assert second.status_code == 409 and "already waiting" in second.json()["detail"]
    assert len(sent) == 1

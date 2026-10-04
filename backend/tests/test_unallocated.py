"""Money with no invoice behind it: how it shows up, and how a bursar resolves it."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.enums import InvoiceStatus, PaymentMethod, PaymentStatus
from app.models.invoice import Invoice
from app.models.job import Job
from app.models.payment import AuditLog, Payment
from app.models.student import Student, Term
from app.services import payment_service as ps
from tests.conftest import needs_db

pytestmark = needs_db
D = Decimal


def _unallocated(db, w, amount="500", ref="RCPX"):
    """The state the M-Pesa callback leaves behind when nothing was left to pay."""
    ps.create_pending_mpesa_payment(db, w.school.id, w.student.id, None, D(amount), "ws_CO_u")
    ps.record_confirmed_payment(db, w.school.id, w.student.id, D("10000"), PaymentMethod.CASH, invoice_id=w.invoice.id)
    ps.resolve_mpesa_callback(db, "ws_CO_u", 0, ref, paid_amount=int(amount))
    return db.execute(select(Payment).where(Payment.reference_code == ref)).scalar_one()


def _new_invoice(db, w, total="3000"):
    term = Term(school_id=w.school.id, name="Term 2", start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc) + timedelta(days=90))
    db.add(term)
    db.flush()
    inv = Invoice(school_id=w.school.id, student_id=w.student.id, term_id=term.id, total_amount=D(total),
                  due_date=datetime.now(timezone.utc) + timedelta(days=60), status=InvoiceStatus.ISSUED)
    db.add(inv)
    db.commit()
    return inv


def test_nothing_unallocated_by_default(db, world):
    assert ps.list_unallocated_payments(db, world.school.id) == []


def test_unallocated_payment_is_listed_with_the_invoices_it_could_go_to(db, world):
    pay = _unallocated(db, world, "500")
    nxt = _new_invoice(db, world, "3000")
    [row] = ps.list_unallocated_payments(db, world.school.id)
    assert row["id"] == pay.id and row["amount"] == D("500.00") and row["student_name"] == "Kid One"
    assert row["reference_code"] == "RCPX" and row["admission_number"] == "1001"
    assert [o["id"] for o in row["open_invoices"]] == [nxt.id] and row["open_invoices"][0]["balance"] == D("3000.00")


def test_list_is_scoped_to_one_school(db, world):
    _unallocated(db, world)
    assert ps.list_unallocated_payments(db, "some-other-school") == []


def test_apply_whole_payment_to_a_new_invoice(db, world):
    pay = _unallocated(db, world, "500")
    nxt = _new_invoice(db, world, "3000")
    jobs_before = db.execute(select(func.count()).select_from(Job)).scalar_one()

    applied = ps.apply_unallocated_payment(db, world.school.id, pay.id, nxt.id, world.bursar.id)

    assert applied.invoice_id == nxt.id and applied.amount == D("500.00") and applied.reference_code == "RCPX"
    db.expire_all()
    inv = db.get(Invoice, nxt.id)
    assert inv.amount_paid == D("500.00") and inv.status == InvoiceStatus.PARTIALLY_PAID
    assert ps.list_unallocated_payments(db, world.school.id) == []  # off the to-do list
    assert db.get(Payment, pay.id).status == PaymentStatus.REVERSED  # ledger kept, not edited away
    assert db.execute(select(func.count()).select_from(Job)).scalar_one() == jobs_before  # parent not re-notified
    assert "PAYMENT_ALLOCATED" in [a.action for a in db.execute(select(AuditLog)).scalars()]


def test_ledger_nets_to_the_money_actually_received(db, world):
    pay = _unallocated(db, world, "500")
    nxt = _new_invoice(db, world, "3000")
    ps.apply_unallocated_payment(db, world.school.id, pay.id, nxt.id)
    total = db.execute(select(func.sum(Payment.amount)).where(
        Payment.student_id == world.student.id, Payment.status.in_([PaymentStatus.CONFIRMED, PaymentStatus.REVERSED]))).scalar_one()
    assert total == D("10500.00")  # 10,000 cash + 500 M-Pesa — nothing created or lost


def test_payment_bigger_than_the_invoice_leaves_a_remainder_still_waiting(db, world):
    pay = _unallocated(db, world, "5000")
    small = _new_invoice(db, world, "2000")
    applied = ps.apply_unallocated_payment(db, world.school.id, pay.id, small.id)
    assert applied.amount == D("2000.00")
    db.expire_all()
    assert db.get(Invoice, small.id).status == InvoiceStatus.PAID
    [row] = ps.list_unallocated_payments(db, world.school.id)
    assert row["amount"] == D("3000.00") and row["reference_code"] == "RCPX"  # the rest is still on the list


def test_cannot_apply_to_another_students_invoice(db, world):
    pay = _unallocated(db, world)
    other = Student(school_id=world.school.id, admission_number="9", full_name="Other Kid")
    db.add(other)
    db.flush()
    term = db.execute(select(Term)).scalars().first()
    inv = Invoice(school_id=world.school.id, student_id=other.id, term_id=term.id, total_amount=D("1000"),
                  due_date=datetime.now(timezone.utc), status=InvoiceStatus.ISSUED)
    db.add(inv)
    db.commit()
    with pytest.raises(HTTPException) as e:
        ps.apply_unallocated_payment(db, world.school.id, pay.id, inv.id)
    assert e.value.status_code == 422


def test_cannot_apply_to_a_paid_invoice(db, world):
    pay = _unallocated(db, world)
    with pytest.raises(HTTPException) as e:
        ps.apply_unallocated_payment(db, world.school.id, pay.id, world.invoice.id)  # already PAID
    assert e.value.status_code == 422


def test_cannot_apply_twice_or_apply_an_ordinary_payment(db, world):
    pay = _unallocated(db, world)
    nxt = _new_invoice(db, world)
    ps.apply_unallocated_payment(db, world.school.id, pay.id, nxt.id)
    with pytest.raises(HTTPException) as e:
        ps.apply_unallocated_payment(db, world.school.id, pay.id, nxt.id)
    assert e.value.status_code == 422
    normal = db.execute(select(Payment).where(Payment.invoice_id == world.invoice.id)).scalars().first()
    with pytest.raises(HTTPException) as e2:
        ps.apply_unallocated_payment(db, world.school.id, normal.id, nxt.id)
    assert e2.value.status_code == 422


def test_other_schools_payment_is_404(db, world):
    pay = _unallocated(db, world)
    nxt = _new_invoice(db, world)
    with pytest.raises(HTTPException) as e:
        ps.apply_unallocated_payment(db, "some-other-school", pay.id, nxt.id)
    assert e.value.status_code == 404


def test_marking_refunded_uses_reversal_and_clears_the_list(db, world):
    pay = _unallocated(db, world, "500")
    ps.reverse_payment(db, pay.id, "Refunded to payer", world.bursar.id)
    assert ps.list_unallocated_payments(db, world.school.id) == []
    db.expire_all()
    assert db.get(Payment, pay.id).status == PaymentStatus.REVERSED


# --- over HTTP: routing, auth and response shapes ------------------------------


def _client_for(w):
    from fastapi.testclient import TestClient
    from app.core.security import create_access_token
    from app.main import app

    token = create_access_token(w.bursar.id, w.school.id, "BURSAR", token_version=w.bursar.token_version or 0)
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_http_list_apply_and_idempotent_retry(db, world):
    pay = _unallocated(db, world, "500")
    nxt = _new_invoice(db, world, "3000")
    client = _client_for(world)

    listed = client.get("/api/payments/unallocated")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert len(body) == 1 and body[0]["id"] == pay.id and body[0]["open_invoices"][0]["id"] == nxt.id

    headers = {"Idempotency-Key": "apply-1"}
    first = client.post(f"/api/payments/{pay.id}/apply", json={"invoice_id": nxt.id}, headers=headers)
    assert first.status_code == 201, first.text
    assert first.json()["invoice_id"] == nxt.id
    retry = client.post(f"/api/payments/{pay.id}/apply", json={"invoice_id": nxt.id}, headers=headers)
    assert retry.status_code == 201 and retry.json() == first.json()  # a double-click is harmless
    assert client.get("/api/payments/unallocated").json() == []


def test_http_parents_cannot_see_or_apply_unallocated_money(db, world):
    from fastapi.testclient import TestClient
    from app.core.security import create_access_token
    from app.main import app

    pay = _unallocated(db, world)
    token = create_access_token(world.parent.id, world.school.id, "PARENT", token_version=world.parent.token_version or 0)
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    assert client.get("/api/payments/unallocated").status_code == 403
    assert client.post(f"/api/payments/{pay.id}/apply", json={"invoice_id": "x"}).status_code == 403

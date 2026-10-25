"""An M-Pesa callback for the wrong amount never credits anything — but it must not vanish either:
it lands in a bursar's list, and the bursar accepts the reported amount or dismisses it."""

from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.main import app
from app.models.enums import InvoiceStatus, PaymentStatus
from app.models.invoice import Invoice
from app.models.job import Job
from app.models.payment import AuditLog, Payment
from app.services import payment_service as ps
from app.services.mpesa_service import MpesaOutcomeUnknown
from tests.conftest import needs_db

pytestmark = needs_db
D = Decimal


@pytest.fixture()
def client(db, world):
    from app.core.rate_limit import limiter

    limiter.reset()
    c = TestClient(app)
    c.headers["Authorization"] = "Bearer " + create_access_token(world.bursar.id, world.school.id, "BURSAR")
    yield c
    limiter.reset()


def _mismatched(db, w, asked="3000", reported=2999, cid="ws_CO_mm", receipt="RCPMM1"):
    payment = ps.create_pending_mpesa_payment(db, w.school.id, w.student.id, w.invoice.id, D(asked), cid)
    assert ps.resolve_mpesa_callback(db, cid, 0, receipt, paid_amount=reported) is None
    return payment


def _invoice(db, w):
    db.expire_all()
    return db.get(Invoice, w.invoice.id)


def test_mismatch_is_listed_with_both_amounts_and_the_receipt(db, world):
    p = _mismatched(db, world)
    rows = ps.list_mpesa_mismatches(db, world.school.id)
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == p.id
    assert row["expected_amount"] == D("3000") and row["reported_amount"] == D("2999")
    assert row["mpesa_receipt"] == "RCPMM1"


def test_repeated_callbacks_do_not_pile_up_audit_rows(db, world):
    _mismatched(db, world)
    for _ in range(3):  # Safaricom retries
        ps.resolve_mpesa_callback(db, "ws_CO_mm", 0, "RCPMM1", paid_amount=2999)
    n = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == ps.MISMATCH_AUDIT_ACTION))
    assert n == 1


def test_a_normal_pending_payment_is_not_listed(db, world):
    ps.create_pending_mpesa_payment(db, world.school.id, world.student.id, world.invoice.id, D("3000"), "ws_CO_ok")
    assert ps.list_mpesa_mismatches(db, world.school.id) == []


def test_accept_records_the_reported_amount_and_tells_the_parent(db, world):
    p = _mismatched(db, world)
    jobs_before = db.scalar(select(func.count()).select_from(Job))
    done = ps.accept_mpesa_mismatch(db, world.school.id, p.id, world.bursar.id)
    assert done.status == PaymentStatus.CONFIRMED and done.amount == D("2999") and done.reference_code == "RCPMM1"
    inv = _invoice(db, world)
    assert inv.amount_paid == D("2999.00") and inv.status == InvoiceStatus.PARTIALLY_PAID
    assert db.scalar(select(func.count()).select_from(Job)) == jobs_before + 1  # "payment received" queued
    assert ps.list_mpesa_mismatches(db, world.school.id) == []


def test_accepting_more_than_was_asked_never_overpays_an_invoice(db, world):
    p = _mismatched(db, world, asked="3000", reported=12000)  # invoice only owes 10,000
    ps.accept_mpesa_mismatch(db, world.school.id, p.id, world.bursar.id)
    inv = _invoice(db, world)
    assert inv.amount_paid == D("10000.00") and inv.status == InvoiceStatus.PAID
    leftover = ps.list_unallocated_payments(db, world.school.id)
    assert len(leftover) == 1 and leftover[0]["amount"] == D("2000")  # surfaced for the bursar, not lost


def test_accept_twice_is_refused(db, world):
    from fastapi import HTTPException

    p = _mismatched(db, world)
    ps.accept_mpesa_mismatch(db, world.school.id, p.id, world.bursar.id)
    with pytest.raises(HTTPException) as e:
        ps.accept_mpesa_mismatch(db, world.school.id, p.id, world.bursar.id)
    assert e.value.status_code == 422
    assert _invoice(db, world).amount_paid == D("2999.00")  # not 5998


def test_dismiss_marks_failed_credits_nothing_and_stays_quiet(db, world):
    p = _mismatched(db, world)
    jobs_before = db.scalar(select(func.count()).select_from(Job))
    done = ps.dismiss_mpesa_mismatch(db, world.school.id, p.id, "handled outside Ledgr", world.bursar.id)
    assert done.status == PaymentStatus.FAILED and "handled outside Ledgr" in done.notes
    assert _invoice(db, world).amount_paid == 0
    assert db.scalar(select(func.count()).select_from(Job)) == jobs_before
    assert ps.list_mpesa_mismatches(db, world.school.id) == []


def test_an_ordinary_pending_payment_cannot_be_accepted_or_dismissed(db, world):
    from fastapi import HTTPException

    p = ps.create_pending_mpesa_payment(db, world.school.id, world.student.id, world.invoice.id, D("3000"), "ws_CO_plain")
    for call in (
        lambda: ps.accept_mpesa_mismatch(db, world.school.id, p.id),
        lambda: ps.dismiss_mpesa_mismatch(db, world.school.id, p.id, "because"),
    ):
        with pytest.raises(HTTPException) as e:
            call()
        assert e.value.status_code == 422


def test_another_schools_bursar_cannot_touch_it(db, world):
    from fastapi import HTTPException

    p = _mismatched(db, world)
    with pytest.raises(HTTPException) as e:
        ps.accept_mpesa_mismatch(db, "some-other-school", p.id)
    assert e.value.status_code == 404


def test_http_list_accept_and_dismiss(db, world, client):
    p = _mismatched(db, world)
    listed = client.get("/api/payments/mpesa-mismatches")
    assert listed.status_code == 200 and listed.json()[0]["id"] == p.id

    parent_headers = {"Authorization": "Bearer " + create_access_token(world.parent.id, world.school.id, "PARENT")}
    assert client.get("/api/payments/mpesa-mismatches", headers=parent_headers).status_code == 403

    bad = client.post(f"/api/payments/{p.id}/dismiss-mpesa", json={"reason": "x"})
    assert bad.status_code == 422  # reason too short
    ok = client.post(f"/api/payments/{p.id}/accept-mpesa-amount")
    assert ok.status_code == 201 and ok.json()["status"] == "CONFIRMED"


# --- STK push: the payment is recorded BEFORE the phone is prompted -------------------------------


@pytest.fixture()
def stk(db, world, client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "mpesa_callback_url", "https://api.example/cb?token=s")
    state = {"rows_when_called": None}

    async def fake_push(**kwargs):
        # Look at the database from inside the "call to Safaricom".
        from app.core.database import SystemSessionLocal

        with SystemSessionLocal() as s:
            state["rows_when_called"] = [(p.status, p.external_txn_id) for p in s.execute(select(Payment)).scalars()]
        if state.get("raise_exc"):
            raise state["raise_exc"]
        return state.get("result", {"CheckoutRequestID": "ws_CO_real"})

    monkeypatch.setattr("app.routers.mpesa.initiate_stk_push", fake_push)
    state["post"] = lambda: client.post(
        "/api/payments/mpesa/stk-push", json={"invoice_id": world.invoice.id, "phone_number": "0712345678", "amount": "3000"}
    )
    return state


def _payments(db):
    db.expire_all()
    return db.execute(select(Payment)).scalars().all()


def test_the_row_exists_before_safaricom_is_called_and_gets_the_real_id_after(db, world, stk):
    res = stk["post"]()
    assert res.status_code == 201 and res.json()["checkout_request_id"] == "ws_CO_real"
    (status, placeholder), = stk["rows_when_called"]
    assert status == PaymentStatus.PENDING and placeholder.startswith(ps.UNSENT_PREFIX)
    (row,) = _payments(db)
    assert row.external_txn_id == "ws_CO_real"
    # ...and the callback can now find it
    assert ps.resolve_mpesa_callback(db, "ws_CO_real", 0, "RCPX", paid_amount=3000) is not None


def test_a_refused_push_leaves_no_row_and_no_leaked_detail(db, world, stk):
    stk["raise_exc"] = RuntimeError("Daraja STK push failed (400): {'errorMessage': 'Bad Request - secret detail'}")
    res = stk["post"]()
    assert res.status_code == 502
    assert "secret detail" not in res.text and "Daraja" not in res.text
    assert _payments(db) == []


def test_a_lost_reply_keeps_the_row_flagged_instead_of_guessing(db, world, stk):
    stk["raise_exc"] = MpesaOutcomeUnknown("ReadTimeout")
    res = stk["post"]()
    assert res.status_code == 502 and "Check your phone" in res.json()["detail"]
    (row,) = _payments(db)
    assert row.status == PaymentStatus.PENDING and "outcome unknown" in row.notes


def test_missing_checkout_id_is_treated_as_a_refusal(db, world, stk):
    stk["result"] = {"ResponseDescription": "weird"}
    assert stk["post"]().status_code == 502
    assert _payments(db) == []


def test_discard_never_deletes_a_payment_that_has_a_real_checkout_id(db, world):
    p = ps.create_pending_mpesa_payment(db, world.school.id, world.student.id, world.invoice.id, D("3000"), "ws_CO_real2")
    ps.discard_unsent_payment(db, p.id)
    assert db.get(Payment, p.id) is not None

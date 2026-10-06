"""A bursar at school A must never be able to touch school B's data — even with RLS off.

Row-Level Security is the second wall, and it only exists when APP_DATABASE_URL points at the
restricted role. These tests run as the table OWNER (no RLS at all, same as an app that was
deployed without APP_DATABASE_URL), so they prove the application-level school check holds
by itself. If one of these starts failing, a school-scoped query lost its `school_id` filter.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.main import app
from app.models.enums import FeeCategory, InvoiceStatus, PaymentMethod, PaymentStatus, UserRole
from app.models.invoice import FeeStructure, Invoice
from app.models.payment import Payment
from app.models.school import School, User
from app.models.student import Student, Term
from app.services import payment_service as ps
from app.services.invoice_service import generate_invoice_for_student
from tests.conftest import needs_db

pytestmark = needs_db

D = Decimal


@pytest.fixture()
def rival(db):
    """A second, unrelated school with a student who has a payment, plus a student with no
    invoice yet (and a fee structure, so generating one WOULD succeed if nothing stopped it)."""
    school = School(name="Rival Academy", country="KE", contact_email="office@rival.example")
    db.add(school)
    db.flush()
    term = Term(
        school_id=school.id, name="Rival Term", start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=90),
    )
    billed = Student(school_id=school.id, admission_number="9001", full_name="Rival Kid")
    unbilled = Student(school_id=school.id, admission_number="9002", full_name="Rival Kid Two")
    db.add_all([term, billed, unbilled])
    db.flush()
    invoice = Invoice(
        school_id=school.id, student_id=billed.id, term_id=term.id, total_amount=D("5000.00"),
        due_date=datetime.now(timezone.utc) + timedelta(days=30), status=InvoiceStatus.ISSUED,
    )
    db.add_all([
        invoice,
        FeeStructure(school_id=school.id, term_id=term.id, category=FeeCategory.TUITION, name="Tuition", amount=D("5000.00")),
    ])
    db.commit()
    payment = ps.record_confirmed_payment(db, school.id, billed.id, D("1000"), PaymentMethod.CASH, invoice_id=invoice.id)

    class R:
        pass

    r = R()
    r.school, r.term, r.billed, r.unbilled, r.invoice, r.payment = school, term, billed, unbilled, invoice, payment
    return r


@pytest.fixture()
def client(db, world):
    from app.core.rate_limit import limiter

    limiter.reset()
    c = TestClient(app)
    # A real bursar of school A (the `world` school).
    c.headers["Authorization"] = "Bearer " + create_access_token(world.bursar.id, world.school.id, "BURSAR")
    yield c
    limiter.reset()


def _payment_state(db, payment_id):
    db.expire_all()
    status = db.get(Payment, payment_id).status
    reversals = db.scalar(select(func.count()).select_from(Payment).where(Payment.reversal_of_id == payment_id))
    return status, reversals


# --- reversing a payment ---------------------------------------------------------------------


def test_http_bursar_cannot_reverse_another_schools_payment(db, world, rival, client):
    res = client.post(f"/api/payments/{rival.payment.id}/reverse", json={"reason": "attack on rival"})
    assert res.status_code == 404
    assert _payment_state(db, rival.payment.id) == (PaymentStatus.CONFIRMED, 0)  # untouched


def test_service_reverse_payment_refuses_another_schools_payment(db, world, rival):
    with pytest.raises(HTTPException) as e:
        ps.reverse_payment(db, world.school.id, rival.payment.id, "not mine")
    assert e.value.status_code == 404
    assert _payment_state(db, rival.payment.id) == (PaymentStatus.CONFIRMED, 0)


def test_http_bursar_can_still_reverse_their_own_schools_payment(db, world, client):
    own = ps.record_confirmed_payment(
        db, world.school.id, world.student.id, D("500"), PaymentMethod.CASH, invoice_id=world.invoice.id
    )
    res = client.post(f"/api/payments/{own.id}/reverse", json={"reason": "entered twice"})
    assert res.status_code == 201
    assert _payment_state(db, own.id) == (PaymentStatus.REVERSED, 1)


# --- creating an invoice ---------------------------------------------------------------------


def _rival_invoice_count(db, rival):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(Invoice).where(Invoice.student_id == rival.unbilled.id))


def test_http_bursar_cannot_invoice_another_schools_student(db, world, rival, client):
    res = client.post("/api/invoices", json={
        "student_id": rival.unbilled.id, "term_id": rival.term.id,
        "due_date": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
    })
    assert res.status_code == 404
    assert _rival_invoice_count(db, rival) == 0


def test_service_generate_invoice_refuses_another_schools_student(db, world, rival):
    with pytest.raises(HTTPException) as e:
        generate_invoice_for_student(
            db, world.school.id, rival.unbilled.id, rival.term.id, datetime.now(timezone.utc) + timedelta(days=14)
        )
    assert e.value.status_code == 404
    assert _rival_invoice_count(db, rival) == 0


def test_service_generate_invoice_still_works_for_own_school(db, world):
    from app.models.student import Student as S

    kid = S(school_id=world.school.id, admission_number="2002", full_name="Kid Two")
    db.add(kid)
    db.add(FeeStructure(school_id=world.school.id, term_id=world.term.id, category=FeeCategory.TUITION, name="Tuition", amount=D("8000.00")))
    db.commit()
    inv = generate_invoice_for_student(db, world.school.id, kid.id, world.term.id, datetime.now(timezone.utc) + timedelta(days=14))
    assert inv.school_id == world.school.id and inv.total_amount == D("8000.00")


# --- fee statement ---------------------------------------------------------------------------


def test_http_statement_rejects_another_schools_term(db, world, rival, client):
    res = client.get(f"/api/students/{world.student.id}/statement", params={"term_id": rival.term.id})
    assert res.status_code == 404  # used to answer 200 with the rival school's term name on the PDF


def test_http_statement_works_for_own_term(db, world, client):
    res = client.get(f"/api/students/{world.student.id}/statement", params={"term_id": world.term.id})
    assert res.status_code == 200

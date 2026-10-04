"""The parent dashboard must cost a FIXED number of database queries however many children
and invoices the parent has. Each query is a network round trip to the hosted database, so
this is what keeps the page fast for families with several children."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.core.database import system_engine
from app.core.deps import CurrentUser
from app.models.enums import GuardianLinkStatus, InvoiceStatus, PaymentMethod
from app.models.invoice import Invoice
from app.models.student import SchoolClass, Student, StudentGuardian, Term
from app.routers import parent as parent_router
from app.services import payment_service as ps
from tests.conftest import needs_db

pytestmark = needs_db
D = Decimal
MAX_QUERIES = 7  # links, students, classes, invoices, items, payments, plans — one per table


def _family(db, w, extra_children: int):
    """The fixture's child plus `extra_children` more, each with two invoices and a part-payment."""
    cls = SchoolClass(school_id=w.school.id, name="Grade 4")
    db.add(cls)
    db.flush()
    w.student.class_id = cls.id
    kids = [w.student]
    for i in range(extra_children):
        kid = Student(school_id=w.school.id, admission_number=f"20{i}", full_name=f"Sibling {i}", class_id=cls.id)
        db.add(kid)
        db.flush()
        kids.append(kid)
    for kid in kids:
        db.add(StudentGuardian(student_id=kid.id, user_id=w.parent.id, relationship_type="mother", status=GuardianLinkStatus.APPROVED))
    db.commit()
    for kid in kids[1:]:
        for n in range(2):
            term = Term(school_id=w.school.id, name=f"T{n}", start_date=datetime.now(timezone.utc), end_date=datetime.now(timezone.utc) + timedelta(days=90))
            db.add(term)
            db.flush()
            inv = Invoice(school_id=w.school.id, student_id=kid.id, term_id=term.id, total_amount=D("5000"),
                          due_date=datetime.now(timezone.utc) + timedelta(days=10 * (n + 1)), status=InvoiceStatus.ISSUED)
            db.add(inv)
            db.commit()
            ps.record_confirmed_payment(db, w.school.id, kid.id, D("1000"), PaymentMethod.CASH, invoice_id=inv.id)
    return kids


def _fetch(db, w):
    # Read these first: after a commit they are expired, and touching them would run
    # refresh queries that belong to the test, not to the endpoint being measured.
    user = CurrentUser(user_id=w.parent.id, school_id=w.school.id, role="PARENT")
    school_id = w.school.id
    count = {"n": 0}

    def _count(*_a, **_k):
        count["n"] += 1

    event.listen(system_engine, "before_cursor_execute", _count)
    try:
        result = parent_router.list_my_children(db=db, user=user, _school_id=school_id)
    finally:
        event.remove(system_engine, "before_cursor_execute", _count)
    return result, count["n"]


@pytest.mark.parametrize("extra", [0, 1, 4])
def test_query_count_does_not_grow_with_the_number_of_children(db, world, extra):
    _family(db, world, extra)
    result, queries = _fetch(db, world)
    assert len(result) == extra + 1
    assert queries <= MAX_QUERIES, f"{queries} queries for {extra + 1} children"


def test_every_child_gets_their_own_invoices_balances_and_payments(db, world):
    kids = _family(db, world, 2)
    result, _ = _fetch(db, world)
    by_name = {c.full_name: c for c in result}
    assert set(by_name) == {"Kid One", "Sibling 0", "Sibling 1"}
    assert all(c.class_name == "Grade 4" for c in result)

    first = by_name["Kid One"]
    assert [inv.total_amount for inv in first.invoices] == [D("10000.00")] and first.balance_due == D("10000.00")

    sib = by_name["Sibling 0"]
    assert len(sib.invoices) == 2 and sib.balance_due == D("8000.00")  # 2 x (5,000 - 1,000)
    assert [inv.due_date for inv in sib.invoices] == sorted((inv.due_date for inv in sib.invoices), reverse=True)  # newest first
    assert all(len(inv.payments) == 1 and inv.payments[0].amount == D("1000.00") for inv in sib.invoices)
    # nothing leaks between siblings
    assert {p.id for inv in sib.invoices for p in inv.payments}.isdisjoint({p.id for inv in by_name["Sibling 1"].invoices for p in inv.payments})
    assert kids[0].id == first.id

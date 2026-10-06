"""Bulk invoice generation: the batched path must give EXACTLY what generating
one student at a time gives — it is only allowed to be faster."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import event, func, select

from app.core.database import system_engine
from app.models.enums import FeeCategory, InvoiceStatus
from app.models.invoice import FeeStructure, Invoice, InvoiceItem
from app.models.student import SchoolClass, Student, Term
from app.services.invoice_service import generate_invoice_for_student, generate_invoices_bulk
from tests.conftest import needs_db

pytestmark = needs_db
D = Decimal


@pytest.fixture()
def school(db, world):
    """3 grades: A (class-specific + school-wide fees), B (school-wide only), C (nothing but school-wide too),
    plus a term with no fee structure at all for the 'nothing defined' case."""
    sid = world.school.id
    term = Term(school_id=sid, name="Term 1 2027", start_date=datetime.now(timezone.utc), end_date=datetime.now(timezone.utc) + timedelta(days=90))
    empty_term = Term(school_id=sid, name="Term 9 (no fees)", start_date=datetime.now(timezone.utc), end_date=datetime.now(timezone.utc) + timedelta(days=90))
    classes = [SchoolClass(school_id=sid, name=n) for n in ("A", "B", "C")]
    db.add_all([term, empty_term, *classes])
    db.flush()
    a, b, c = classes
    db.add_all([
        FeeStructure(school_id=sid, term_id=term.id, category=FeeCategory.TUITION, name="Tuition A", amount=D("30000"), class_id=a.id),
        FeeStructure(school_id=sid, term_id=term.id, category=FeeCategory.TRANSPORT, name="Transport", amount=D("6000")),  # school-wide
        FeeStructure(school_id=sid, term_id=term.id, category=FeeCategory.MEALS, name="Lunch", amount=D("8000")),          # school-wide
        FeeStructure(school_id=sid, term_id=term.id, category=FeeCategory.TUITION, name="Tuition B", amount=D("25000"), class_id=b.id),
    ])
    kids = []
    for i in range(30):
        cls = classes[i % 3]
        kid = Student(school_id=sid, admission_number=f"x{i}", full_name=f"Kid {i}", class_id=cls.id)
        db.add(kid)
        kids.append(kid)
    noclass = Student(school_id=sid, admission_number="noclass", full_name="No Class")  # school-wide fees only
    db.add(noclass)
    kids.append(noclass)
    db.commit()

    class S: pass
    s = S()
    s.sid, s.term, s.empty_term, s.classes, s.kids = sid, term, empty_term, classes, kids
    s.kid_ids = [k.id for k in kids]  # read now: commits expire ORM objects and re-reading costs queries
    s.due = datetime.now(timezone.utc) + timedelta(days=30)
    return s


def _snapshot(db, term_id):
    """Everything that matters about the result, independent of ids and timestamps."""
    rows = db.execute(
        select(Student.admission_number, Invoice.total_amount, Invoice.status, Invoice.due_date, Invoice.amount_paid, Invoice.id)
        .join(Invoice, Invoice.student_id == Student.id).where(Invoice.term_id == term_id).order_by(Student.admission_number)
    ).all()
    out = {}
    for adm, total, status, due, paid, inv_id in rows:
        items = sorted(db.execute(select(FeeStructure.name, InvoiceItem.amount).join(FeeStructure, FeeStructure.id == InvoiceItem.fee_structure_id)
                                  .where(InvoiceItem.invoice_id == inv_id)).all())
        out[adm] = (total, status, due, paid, items)
    return out


def _one_at_a_time(db, s, students, term_id):
    created, errs = 0, []
    for st in students:
        try:
            generate_invoice_for_student(db, st.school_id, st.id, term_id, s.due)
            created += 1
        except Exception as exc:  # noqa: BLE001 — the old endpoint's exact behaviour
            errs.append({"student_id": st.id, "error": str(exc)})
    return created, errs


def test_batched_result_is_identical_to_one_at_a_time(db, school):
    db.execute(Invoice.__table__.delete())
    db.commit()
    old_created, old_errors = _one_at_a_time(db, school, school.kids, school.term.id)
    old = _snapshot(db, school.term.id)

    db.execute(InvoiceItem.__table__.delete())
    db.execute(Invoice.__table__.delete())
    db.commit()
    new_created, new_errors = generate_invoices_bulk(db, school.sid, school.kids, school.term.id, school.due, chunk_size=7)
    new = _snapshot(db, school.term.id)

    assert (new_created, new_errors) == (old_created, old_errors)
    assert new == old and len(new) == 31
    assert new["x0"][0] == D("44000.00") and new["x1"][0] == D("39000.00")  # A: 30k+6k+8k   B: 25k+6k+8k
    assert new["x2"][0] == D("14000.00") and new["noclass"][0] == D("14000.00")  # C / no class: school-wide only
    assert all(v[1] == InvoiceStatus.ISSUED and v[3] == 0 for v in new.values())


def test_already_invoiced_students_are_skipped_with_the_same_message(db, school):
    generate_invoice_for_student(db, school.kids[0].school_id, school.kids[0].id, school.term.id, school.due)
    created, errors = generate_invoices_bulk(db, school.sid, school.kids, school.term.id, school.due)
    assert created == 30  # 31 minus the one that already had an invoice
    assert errors == [{"student_id": school.kids[0].id, "error": "409: An invoice already exists for this student and term"}]
    assert db.execute(select(func.count()).select_from(Invoice).where(Invoice.term_id == school.term.id)).scalar_one() == 31  # no duplicates


def test_running_it_twice_creates_nothing_new(db, school):
    generate_invoices_bulk(db, school.sid, school.kids, school.term.id, school.due)
    created, errors = generate_invoices_bulk(db, school.sid, school.kids, school.term.id, school.due)
    assert created == 0 and len(errors) == 31
    assert db.execute(select(func.count()).select_from(Invoice)).scalar_one() == 31 + 1  # + the fixture's own invoice


def test_term_without_fee_structures_skips_everyone_with_the_same_message(db, school):
    created, errors = generate_invoices_bulk(db, school.sid, school.kids, school.empty_term.id, school.due)
    assert created == 0 and len(errors) == 31
    assert errors[0]["error"] == "422: No fee structure defined for this student's class/term yet"


def test_a_concurrent_run_that_beat_us_to_some_students_is_handled(db, school, monkeypatch):
    """The unique index catches a race; the chunk then falls back to one-by-one so nobody is lost or doubled."""
    from app.services import invoice_service as svc

    real = svc.generate_invoice_for_student
    calls = {"n": 0}

    # Simulate: after our "already invoiced?" check, another request invoices student 3 before our insert.
    original_add_all = db.add_all

    state = {"injected": False}

    def sneaky_add_all(items):
        items = list(items)
        if not state["injected"] and items and isinstance(items[0], Invoice):
            state["injected"] = True
            with svc.SystemSessionLocal() as other:  # a different connection, like another request
                real(other, school.kids[3].school_id, school.kids[3].id, school.term.id, school.due)
        return original_add_all(items)

    monkeypatch.setattr(svc, "SystemSessionLocal", __import__("app.core.database", fromlist=["x"]).SystemSessionLocal, raising=False)
    monkeypatch.setattr(db, "add_all", sneaky_add_all)
    created, errors = generate_invoices_bulk(db, school.sid, school.kids, school.term.id, school.due, chunk_size=100)
    monkeypatch.undo()

    assert created == 30 and len(errors) == 1 and errors[0]["student_id"] == school.kids[3].id
    assert errors[0]["error"].startswith("409")
    per_student = db.execute(select(Invoice.student_id, func.count()).where(Invoice.term_id == school.term.id).group_by(Invoice.student_id)).all()
    assert len(per_student) == 31 and all(n == 1 for _, n in per_student)


def test_database_round_trips_do_not_grow_with_the_number_of_students(db, school):
    count = {"n": 0}

    def _c(*a, **k):
        count["n"] += 1

    sid, term_id, due = school.sid, school.term.id, school.due
    kids = school.kids
    [k.id for k in kids]  # touch (refresh) outside the measured block
    db.refresh(school.term)
    event.listen(system_engine, "before_cursor_execute", _c)
    try:
        generate_invoices_bulk(db, sid, kids, term_id, due, chunk_size=500)
    finally:
        event.remove(system_engine, "before_cursor_execute", _c)
    # 31 students: fee structures, existing invoices, then insert+items+commit for one chunk. The old
    # path was ~5 queries PER student (>150 here).
    assert count["n"] <= 12, count["n"]

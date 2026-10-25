"""The aging report: every unpaid invoice in exactly one bucket, by whole days past its due date."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.models.enums import InvoiceStatus
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.school import School
from app.models.student import SchoolClass, Student, Term
from app.services.aging_service import aging_csv, bucket_for, get_aging_report
from tests.conftest import needs_db

D = Decimal
NOW = lambda: datetime.now(timezone.utc)  # noqa: E731


def test_bucket_boundaries():
    assert [bucket_for(d) for d in (-5, 0, 1, 30, 31, 60, 61, 90, 91, 400)] == [
        "current", "current", "1-30", "1-30", "31-60", "31-60", "61-90", "61-90", "90+", "90+",
    ]


_terms = iter(range(1, 10_000))


def _inv(db, w, *, due_in_days, total="1000", paid="0", status=InvoiceStatus.ISSUED, student=None):
    # One invoice per student per term, so every invoice gets a term of its own.
    term = Term(school_id=w.school.id, name=f"Term {next(_terms)}", start_date=NOW() - timedelta(days=400), end_date=NOW() - timedelta(days=300))
    db.add(term)
    db.flush()
    stu = student or w.student
    inv = Invoice(school_id=w.school.id, student_id=stu.id, term_id=term.id, total_amount=D(total), amount_paid=D(paid),
                  due_date=NOW() + timedelta(days=due_in_days), status=status)
    db.add(inv)
    db.commit()
    return inv


@pytest.fixture()
def clean(db, world):
    """The shared world already has one open invoice; start from none so the numbers below are exact."""
    db.query(Payment).delete()
    db.query(Invoice).delete()
    db.commit()
    return world


@needs_db
def test_each_open_invoice_lands_in_one_bucket_with_its_balance(db, clean):
    w = clean
    _inv(db, w, due_in_days=10, total="500")                      # not yet due
    _inv(db, w, due_in_days=-5, total="1000", paid="400")         # 5 days late, balance 600
    _inv(db, w, due_in_days=-45, total="2000")                    # 31-60
    _inv(db, w, due_in_days=-75, total="3000", status=InvoiceStatus.OVERDUE)  # 61-90
    _inv(db, w, due_in_days=-200, total="4000", paid="1000")      # 90+, balance 3000
    report = get_aging_report(db, w.school.id)

    amounts = {b.key: (b.count, b.amount) for b in report.buckets}
    assert amounts == {"current": (1, D("500")), "1-30": (1, D("600")), "31-60": (1, D("2000")), "61-90": (1, D("3000")), "90+": (1, D("3000"))}
    assert report.total_count == 5 and report.total_outstanding == D("9100")
    assert [b.key for b in report.buckets] == ["current", "1-30", "31-60", "61-90", "90+"]  # always all five, in order


@needs_db
def test_worst_first_and_paid_cancelled_and_draft_invoices_are_left_out(db, clean):
    w = clean
    _inv(db, w, due_in_days=-10, total="900")
    _inv(db, w, due_in_days=-100, total="100")
    _inv(db, w, due_in_days=-300, total="777", status=InvoiceStatus.PAID, paid="777")
    _inv(db, w, due_in_days=-300, total="777", status=InvoiceStatus.CANCELLED)
    _inv(db, w, due_in_days=-300, total="777", status=InvoiceStatus.DRAFT)
    report = get_aging_report(db, w.school.id)
    assert [r.days_overdue for r in report.rows] == [100, 10]
    assert [r.bucket for r in report.rows] == ["90+", "1-30"]
    assert report.total_count == 2


@needs_db
def test_filtering_by_bucket_narrows_the_rows_but_not_the_bucket_totals(db, clean):
    w = clean
    _inv(db, w, due_in_days=-10)
    _inv(db, w, due_in_days=-100)
    report = get_aging_report(db, w.school.id, bucket="90+")
    assert [r.bucket for r in report.rows] == ["90+"]
    assert report.total_count == 2  # the cards still show the whole picture


@needs_db
def test_filtering_by_class(db, clean):
    w = clean
    other_class = SchoolClass(school_id=w.school.id, name="Grade 9")
    db.add(other_class)
    db.flush()
    stu2 = Student(school_id=w.school.id, class_id=other_class.id, admission_number="X9", full_name="Other Kid")
    db.add(stu2)
    db.commit()
    _inv(db, w, due_in_days=-10, total="100")
    _inv(db, w, due_in_days=-10, total="250", student=stu2)
    only = get_aging_report(db, w.school.id, class_id=other_class.id)
    assert [r.student_name for r in only.rows] == ["Other Kid"] and only.total_outstanding == D("250")


@needs_db
def test_rows_are_capped_but_totals_are_complete(db, clean):
    w = clean
    for i in range(5):
        _inv(db, w, due_in_days=-(10 + i))
    report = get_aging_report(db, w.school.id, limit=3)
    assert len(report.rows) == 3 and report.truncated is True and report.total_count == 5


@needs_db
def test_another_schools_invoices_never_appear(db, clean):
    w = clean
    _inv(db, w, due_in_days=-10)
    rival = School(name="Rival", country="KE", contact_email="r@x.test")
    db.add(rival)
    db.commit()
    assert get_aging_report(db, rival.id).total_count == 0


@needs_db
def test_csv_has_a_header_and_one_line_per_invoice(db, clean):
    w = clean
    _inv(db, w, due_in_days=-40, total="1234.5")
    lines = aging_csv(get_aging_report(db, w.school.id)).strip().splitlines()
    assert lines[0].startswith("Student,Admission no.,Class")
    assert len(lines) == 2 and lines[1].endswith(",31-60,1234.50")


@pytest.fixture()
def http(db, world):
    from app.core.rate_limit import limiter

    limiter.reset()
    yield TestClient(app)
    limiter.reset()


@needs_db
def test_http_bursar_gets_the_report_and_a_parent_does_not(db, clean, http):
    w = clean
    _inv(db, w, due_in_days=-40)
    bursar = {"Authorization": "Bearer " + create_access_token(w.bursar.id, w.school.id, "BURSAR")}
    parent = {"Authorization": "Bearer " + create_access_token(w.parent.id, w.school.id, "PARENT")}
    ok = http.get("/api/reports/aging", headers=bursar)
    assert ok.status_code == 200 and ok.json()["total_count"] == 1
    assert http.get("/api/reports/aging?bucket=31-60", headers=bursar).json()["rows"][0]["bucket"] == "31-60"
    assert http.get("/api/reports/aging?bucket=nonsense", headers=bursar).status_code == 422
    assert http.get("/api/reports/aging", headers=parent).status_code == 403
    csv_res = http.get("/api/reports/aging/export", headers=bursar)
    assert csv_res.status_code == 200 and "text/csv" in csv_res.headers["content-type"] and "attachment" in csv_res.headers["content-disposition"]

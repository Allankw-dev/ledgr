"""Aging: how much is owed, and for how long it has been late.

Every unpaid invoice falls into exactly one bucket by how many whole days past its due date it is today. This is
the report a bursar actually works from: the 90+ bucket is the money that is about to be lost.
"""

import csv
import io
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.student import SchoolClass, Student, Term
from app.schemas.aging import AgingBucket, AgingReport, AgingRow
from app.services.invoice_service import OPEN_INVOICE_STATUSES

BUCKETS: list[tuple[str, str]] = [
    ("current", "Not yet due"),
    ("1-30", "1 to 30 days late"),
    ("31-60", "31 to 60 days late"),
    ("61-90", "61 to 90 days late"),
    ("90+", "Over 90 days late"),
]
ROW_LIMIT = 300


def bucket_for(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "1-30"
    if days_overdue <= 60:
        return "31-60"
    if days_overdue <= 90:
        return "61-90"
    return "90+"


def _days_overdue_expr():
    return func.floor(func.extract("epoch", func.now() - Invoice.due_date) / 86400)


def _bucket_expr(days):
    return case((days <= 0, "current"), (days <= 30, "1-30"), (days <= 60, "31-60"), (days <= 90, "61-90"), else_="90+")


def get_aging_report(db: Session, school_id: str, *, bucket: str | None = None, class_id: str | None = None, limit: int = ROW_LIMIT) -> AgingReport:
    balance = Invoice.total_amount - Invoice.amount_paid
    days = _days_overdue_expr()
    bucket_case = _bucket_expr(days)

    base = [
        Invoice.school_id == school_id,
        Invoice.status.in_(OPEN_INVOICE_STATUSES),
        balance > 0,
    ]
    if class_id:
        base.append(Invoice.student_id.in_(select(Student.id).where(Student.class_id == class_id)))

    sums = {
        key: (count, amount)
        for key, count, amount in db.execute(
            select(bucket_case, func.count(), func.coalesce(func.sum(balance), 0)).where(*base).group_by(bucket_case)
        ).all()
    }
    buckets = [AgingBucket(key=k, label=label, count=sums.get(k, (0, 0))[0], amount=Decimal(sums.get(k, (0, 0))[1])) for k, label in BUCKETS]  # type: ignore[arg-type]

    row_filters = list(base)
    if bucket:
        row_filters.append(bucket_case == bucket)
    matching = next((b.count for b in buckets if b.key == bucket), 0) if bucket else sum(b.count for b in buckets)

    rows = db.execute(
        select(Invoice, Student, SchoolClass.name, Term.name, days, balance)
        .join(Student, Student.id == Invoice.student_id)
        .join(SchoolClass, SchoolClass.id == Student.class_id, isouter=True)
        .join(Term, Term.id == Invoice.term_id, isouter=True)
        .where(*row_filters)
        .order_by(days.desc(), balance.desc(), Invoice.id.asc())
        .limit(limit)
    ).all()

    return AgingReport(
        buckets=buckets,
        total_count=sum(b.count for b in buckets),
        total_outstanding=sum((b.amount for b in buckets), Decimal(0)),
        rows=[
            AgingRow(
                invoice_id=inv.id,
                student_id=stu.id,
                student_name=stu.full_name,
                admission_number=stu.admission_number,
                class_name=class_name,
                term_name=term_name,
                due_date=inv.due_date,
                days_overdue=int(d),
                balance=Decimal(bal),
                bucket=bucket_for(int(d)),  # type: ignore[arg-type]
            )
            for inv, stu, class_name, term_name, d, bal in rows
        ],
        truncated=matching > limit,
    )


def aging_csv(report: AgingReport) -> str:
    """Opens cleanly in Excel. Always the full list the filters match, not just the first page on screen."""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Student", "Admission no.", "Class", "Term", "Due date", "Days late", "Bucket", "Balance"])
    for r in report.rows:
        w.writerow([r.student_name, r.admission_number, r.class_name or "", r.term_name or "", r.due_date.date().isoformat(), max(r.days_overdue, 0), r.bucket, f"{r.balance:.2f}"])
    return out.getvalue()

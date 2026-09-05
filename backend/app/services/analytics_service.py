"""
Shared analytics/reporting queries.

Extracted from the dashboard router so the same numbers (headline stats,
collection-by-term, top-risk invoices) can be reused by the AI bursar
assistant's tools without duplicating SQL. Each function here does exactly
what the dashboard endpoint used to do inline — same queries, same
semantics — just callable from anywhere that has a `Session` and a
`school_id`.
"""

from dataclasses import dataclass
from decimal import Decimal

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import InvoiceStatus
from app.models.invoice import Invoice
from app.models.student import Student, SchoolClass, Term
from app.services import ml_data_service
from app.services.risk_scoring import compute_risk_score


@dataclass
class HeadlineStats:
    total_collected: Decimal
    total_outstanding: Decimal
    overdue_count: int
    active_student_count: int


@dataclass
class TermCollection:
    term_id: str
    term_name: str
    total_billed: Decimal
    total_paid: Decimal


@dataclass
class RiskyInvoice:
    invoice_id: str
    student_id: str
    student_name: str
    class_name: str
    balance: Decimal
    risk_score: float
    risk_level: str


@dataclass
class CollectionForecast:
    forecasted_total_paid: Decimal
    method: str
    confidence: str  # "low" | "medium" — deliberately never "high", see forecast_next_term_collection
    based_on_terms: int


def get_headline_stats(db: Session, school_id: str) -> HeadlineStats:
    """Total collected/outstanding, overdue invoice count, active student count."""
    totals_row = db.execute(
        select(
            func.coalesce(func.sum(Invoice.amount_paid), 0),
            func.coalesce(func.sum(Invoice.total_amount - Invoice.amount_paid), 0),
            func.count().filter(Invoice.status == InvoiceStatus.OVERDUE),
        ).where(Invoice.school_id == school_id)
    ).one()
    total_collected, total_outstanding, overdue_count = totals_row

    active_student_count = db.execute(
        select(func.count()).select_from(Student).where(Student.school_id == school_id, Student.is_active == True)  # noqa: E712
    ).scalar_one()

    return HeadlineStats(
        total_collected=total_collected,
        total_outstanding=total_outstanding,
        overdue_count=overdue_count,
        active_student_count=active_student_count,
    )


def get_collection_by_term(db: Session, school_id: str) -> list[TermCollection]:
    """Total billed vs. total paid, one row per term, ordered chronologically."""
    term_rows = db.execute(
        select(
            Term.id,
            Term.name,
            func.coalesce(func.sum(Invoice.total_amount), 0),
            func.coalesce(func.sum(Invoice.amount_paid), 0),
        )
        .outerjoin(Invoice, Invoice.term_id == Term.id)
        .where(Term.school_id == school_id)
        .group_by(Term.id, Term.name, Term.start_date)
        .order_by(Term.start_date)
    ).all()

    return [
        TermCollection(term_id=tid, term_name=name, total_billed=billed, total_paid=paid)
        for tid, name, billed, paid in term_rows
    ]


def get_top_risk_invoices(db: Session, school_id: str, limit: int = 5, candidate_pool: int = 30) -> list[RiskyInvoice]:
    """Highest-risk unpaid invoices, scored via risk_scoring.compute_risk_score.

    Risk scoring does real per-invoice computation (queries the student's
    payment history), so it's bounded to a candidate pool rather than
    scoring every unpaid invoice in the school — most-overdue-first is a
    cheap pre-filter that reliably contains the truly high-risk ones.
    """
    candidates = db.execute(
        select(Invoice, Student, SchoolClass)
        .join(Student, Invoice.student_id == Student.id)
        .outerjoin(SchoolClass, Student.class_id == SchoolClass.id)
        .where(
            Invoice.school_id == school_id,
            Invoice.status.notin_([InvoiceStatus.PAID, InvoiceStatus.CANCELLED]),
            Invoice.total_amount > Invoice.amount_paid,
        )
        .order_by(Invoice.due_date)
        .limit(candidate_pool)
    ).all()

    scored = []
    for invoice, student, school_class in candidates:
        assessment = compute_risk_score(db, student.id, invoice.id)
        ml_data_service.log_risk_snapshot(db, school_id, invoice.id, assessment)
        scored.append(
            RiskyInvoice(
                invoice_id=invoice.id,
                student_id=student.id,
                student_name=student.full_name,
                class_name=school_class.name if school_class else "—",
                balance=invoice.total_amount - invoice.amount_paid,
                risk_score=assessment.score,
                risk_level=assessment.level,
            )
        )
    return sorted(scored, key=lambda r: r.risk_score, reverse=True)[:limit]


def forecast_next_term_collection(db: Session, school_id: str) -> CollectionForecast | None:
    """Simple linear-trend forecast of next term's total collections, over
    the same per-term totals get_collection_by_term already computes.

    Deliberately NOT a fancier time-series model (e.g. Holt-Winters,
    ARIMA): with only a handful of terms per school, a heavier model would
    just be overfitting three or four data points with extra steps. A
    straight line through actual history is honest about how little there
    is to go on — reflected in `confidence`, which never reports "high".

    Returns None if there isn't at least 2 terms of real (billed) history
    to extrapolate a trend from.
    """
    terms = get_collection_by_term(db, school_id)
    history = [t for t in terms if t.total_billed > 0]

    if len(history) < 2:
        return None

    paid_values = np.array([float(t.total_paid) for t in history])
    x = np.arange(len(paid_values))

    slope, intercept = np.polyfit(x, paid_values, 1)
    forecast = max(0.0, slope * len(paid_values) + intercept)

    return CollectionForecast(
        forecasted_total_paid=Decimal(str(round(forecast, 2))),
        method="linear_trend",
        confidence="low" if len(history) < 4 else "medium",
        based_on_terms=len(history),
    )

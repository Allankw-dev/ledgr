"""Shared read-only aggregate queries over school data. Used by both the
/api/reports/analytics endpoint (for the dashboard) and the AI assistant's
tools (for natural-language Q&A) — one source of truth for what "total
collected" or "top risk" mean, so the chatbot's answers can never drift
from what the dashboard shows."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import InvoiceStatus
from app.models.invoice import Invoice
from app.models.student import SchoolClass, Student, Term
from app.services.risk_scoring import compute_risk_score

# Risk scoring does real per-invoice computation (queries the student's
# payment history), so callers bound it to a candidate pool rather than
# scoring every unpaid invoice in the school — most-overdue-first is a
# cheap pre-filter that reliably contains the truly high-risk ones.
RISK_CANDIDATE_POOL = 30


@dataclass
class SummaryStats:
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
class RiskInvoice:
    invoice_id: str
    student_id: str
    student_name: str
    class_name: str
    balance: Decimal
    risk_score: float
    risk_level: str


def get_summary_stats(db: Session, school_id: str) -> SummaryStats:
    total_collected, total_outstanding, overdue_count = db.execute(
        select(
            func.coalesce(func.sum(Invoice.amount_paid), 0),
            func.coalesce(func.sum(Invoice.total_amount - Invoice.amount_paid), 0),
            func.count().filter(Invoice.status == InvoiceStatus.OVERDUE),
        ).where(Invoice.school_id == school_id)
    ).one()

    active_student_count = db.execute(
        select(func.count()).select_from(Student).where(Student.school_id == school_id, Student.is_active == True)  # noqa: E712
    ).scalar_one()

    return SummaryStats(
        total_collected=total_collected,
        total_outstanding=total_outstanding,
        overdue_count=overdue_count,
        active_student_count=active_student_count,
    )


def get_collection_by_term(db: Session, school_id: str) -> list[TermCollection]:
    rows = db.execute(
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
    return [TermCollection(term_id=tid, term_name=name, total_billed=billed, total_paid=paid) for tid, name, billed, paid in rows]


def get_top_risk_invoices(db: Session, school_id: str, limit: int = 5, class_id: str | None = None) -> list[RiskInvoice]:
    filters = [
        Invoice.school_id == school_id,
        Invoice.status.notin_([InvoiceStatus.PAID, InvoiceStatus.CANCELLED]),
        Invoice.total_amount > Invoice.amount_paid,
    ]
    if class_id:
        filters.append(Student.class_id == class_id)

    candidates = db.execute(
        select(Invoice, Student, SchoolClass)
        .join(Student, Invoice.student_id == Student.id)
        .outerjoin(SchoolClass, Student.class_id == SchoolClass.id)
        .where(*filters)
        .order_by(Invoice.due_date)
        .limit(RISK_CANDIDATE_POOL)
    ).all()

    scored = []
    for invoice, student, school_class in candidates:
        assessment = compute_risk_score(db, student.id, invoice.id)
        scored.append(
            RiskInvoice(
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


def get_overdue_invoices(db: Session, school_id: str, class_id: str | None = None, limit: int = 20) -> list[dict]:
    filters = [Invoice.school_id == school_id, Invoice.status == InvoiceStatus.OVERDUE]
    if class_id:
        filters.append(Student.class_id == class_id)

    rows = db.execute(
        select(Invoice, Student, SchoolClass)
        .join(Student, Invoice.student_id == Student.id)
        .outerjoin(SchoolClass, Student.class_id == SchoolClass.id)
        .where(*filters)
        .order_by(Invoice.due_date)
        .limit(limit)
    ).all()

    return [
        {
            "student_name": student.full_name,
            "admission_number": student.admission_number,
            "class_name": school_class.name if school_class else "—",
            "balance": str(invoice.total_amount - invoice.amount_paid),
            "due_date": invoice.due_date.date().isoformat(),
        }
        for invoice, student, school_class in rows
    ]


def search_students(db: Session, school_id: str, query: str, limit: int = 10) -> list[dict]:
    """Look up students by name or admission number and summarize their
    current balance across all their invoices — the kind of one-off lookup
    a bursar does dozens of times a day ('has the Otieno boy paid yet?')."""
    like = f"%{query}%"
    matches = db.execute(
        select(Student, SchoolClass)
        .outerjoin(SchoolClass, Student.class_id == SchoolClass.id)
        .where(
            Student.school_id == school_id,
            Student.is_active == True,  # noqa: E712
            (Student.full_name.ilike(like)) | (Student.admission_number.ilike(like)),
        )
        .limit(limit)
    ).all()

    results = []
    for student, school_class in matches:
        totals = db.execute(
            select(
                func.coalesce(func.sum(Invoice.total_amount), 0),
                func.coalesce(func.sum(Invoice.amount_paid), 0),
            ).where(Invoice.student_id == student.id)
        ).one()
        billed, paid = totals
        results.append(
            {
                "student_name": student.full_name,
                "admission_number": student.admission_number,
                "class_name": school_class.name if school_class else "—",
                "total_billed": str(billed),
                "total_paid": str(paid),
                "balance": str(billed - paid),
            }
        )
    return results


def resolve_class_id(db: Session, school_id: str, class_name: str) -> str | None:
    """Best-effort name -> id lookup so tool calls can take a human class
    name ('Grade 4') instead of requiring the model to already know ids."""
    return db.execute(
        select(SchoolClass.id).where(SchoolClass.school_id == school_id, SchoolClass.name.ilike(f"%{class_name}%"))
    ).scalar()

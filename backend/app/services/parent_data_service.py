"""Read-only queries for the parent AI assistant — every function here
takes guardian_user_id (from the caller's own JWT) and resolves it through
student_guardians itself. None of these accept a student_id from outside,
mirroring the same rule parent.py's list_my_children enforces: the link
table is the only source of truth for what a parent can see, never a
client-supplied id — including one an LLM might be tricked into passing."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceItem, FeeStructure
from app.models.payment import Payment
from app.models.student import SchoolClass, Student, StudentGuardian, Term
from app.services.payment_plan_service import recommend_payment_plan


def _my_student_ids(db: Session, guardian_user_id: str) -> list[str]:
    return db.execute(
        select(StudentGuardian.student_id).where(StudentGuardian.user_id == guardian_user_id)
    ).scalars().all()


def _resolve_student_ids(db: Session, guardian_user_id: str, student_name: str | None) -> list[str]:
    """If a name is given, narrows to children matching it (still only
    within this parent's own linked children) — if it matches nothing,
    returns an empty list rather than silently falling back to 'all
    children', so the tool can report 'no child by that name' honestly."""
    my_ids = _my_student_ids(db, guardian_user_id)
    if not my_ids:
        return []
    if not student_name:
        return my_ids

    matched = db.execute(
        select(Student.id).where(Student.id.in_(my_ids), Student.full_name.ilike(f"%{student_name}%"))
    ).scalars().all()
    return matched


def get_children_overview(db: Session, guardian_user_id: str) -> list[dict]:
    student_ids = _my_student_ids(db, guardian_user_id)
    if not student_ids:
        return []

    rows = db.execute(
        select(Student, SchoolClass).outerjoin(SchoolClass, Student.class_id == SchoolClass.id).where(Student.id.in_(student_ids))
    ).all()

    overview = []
    for student, school_class in rows:
        invoices = db.execute(select(Invoice).where(Invoice.student_id == student.id)).scalars().all()
        total_billed = sum((inv.total_amount for inv in invoices), Decimal("0"))
        total_paid = sum((inv.amount_paid for inv in invoices), Decimal("0"))
        overdue_count = sum(1 for inv in invoices if inv.status.value == "OVERDUE")
        overview.append(
            {
                "student_name": student.full_name,
                "class_name": school_class.name if school_class else "—",
                "total_billed": str(total_billed),
                "total_paid": str(total_paid),
                "balance": str(total_billed - total_paid),
                "overdue_invoice_count": overdue_count,
            }
        )
    return overview


def get_payment_history(db: Session, guardian_user_id: str, student_name: str | None = None, limit: int = 10) -> list[dict]:
    student_ids = _resolve_student_ids(db, guardian_user_id, student_name)
    if not student_ids:
        return []

    rows = db.execute(
        select(Payment, Student)
        .join(Student, Payment.student_id == Student.id)
        .where(Payment.student_id.in_(student_ids))
        .order_by(Payment.created_at.desc())
        .limit(limit)
    ).all()

    return [
        {
            "student_name": student.full_name,
            "amount": str(payment.amount),
            "method": payment.method.value,
            "status": payment.status.value,
            "reference_code": payment.reference_code,
            "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
        }
        for payment, student in rows
    ]


def get_invoice_details(db: Session, guardian_user_id: str, student_name: str | None = None) -> list[dict]:
    student_ids = _resolve_student_ids(db, guardian_user_id, student_name)
    if not student_ids:
        return []

    rows = db.execute(
        select(Invoice, Student)
        .join(Student, Invoice.student_id == Student.id)
        .where(Invoice.student_id.in_(student_ids))
        .order_by(Invoice.due_date.desc())
    ).all()

    return [
        {
            "student_name": student.full_name,
            "due_date": invoice.due_date.date().isoformat(),
            "total_amount": str(invoice.total_amount),
            "amount_paid": str(invoice.amount_paid),
            "balance": str(invoice.total_amount - invoice.amount_paid),
            "status": invoice.status.value,
        }
        for invoice, student in rows
    ]


def get_invoice_breakdown(db: Session, guardian_user_id: str, student_name: str | None = None) -> list[dict]:
    """Itemized charges per invoice — what get_invoice_details deliberately
    leaves out to stay compact for the common 'what's due' question. This
    is the tool for 'why is my balance X' or 'what am I actually being
    charged for', where the itemization is the whole point."""
    student_ids = _resolve_student_ids(db, guardian_user_id, student_name)
    if not student_ids:
        return []

    invoices = db.execute(
        select(Invoice, Student)
        .join(Student, Invoice.student_id == Student.id)
        .where(Invoice.student_id.in_(student_ids))
        .order_by(Invoice.due_date.desc())
    ).all()

    result = []
    for invoice, student in invoices:
        item_rows = db.execute(
            select(InvoiceItem, FeeStructure)
            .join(FeeStructure, InvoiceItem.fee_structure_id == FeeStructure.id)
            .where(InvoiceItem.invoice_id == invoice.id)
        ).all()
        result.append(
            {
                "student_name": student.full_name,
                "due_date": invoice.due_date.date().isoformat(),
                "status": invoice.status.value,
                "balance": str(invoice.total_amount - invoice.amount_paid),
                "items": [
                    {"name": fee_structure.name, "category": fee_structure.category.value, "amount": str(item.amount)}
                    for item, fee_structure in item_rows
                ],
            }
        )
    return result


def get_term_summary(db: Session, guardian_user_id: str, student_name: str | None = None) -> list[dict]:
    """One row per term this family has been billed in — for 'how much did
    we pay this term' / 'summarize this term' / 'how does this term
    compare to last term' questions, which get_invoice_details can't
    answer well since it only lists individual invoices, not aggregates."""
    student_ids = _resolve_student_ids(db, guardian_user_id, student_name)
    if not student_ids:
        return []

    rows = db.execute(
        select(Invoice, Term)
        .join(Term, Invoice.term_id == Term.id)
        .where(Invoice.student_id.in_(student_ids))
    ).all()

    by_term: dict[str, dict] = {}
    for invoice, term in rows:
        bucket = by_term.setdefault(
            term.name,
            {"term_name": term.name, "start_date": term.start_date, "total_billed": Decimal("0"), "total_paid": Decimal("0"), "invoice_count": 0},
        )
        bucket["total_billed"] += invoice.total_amount
        bucket["total_paid"] += invoice.amount_paid
        bucket["invoice_count"] += 1

    ordered = sorted(by_term.values(), key=lambda b: b["start_date"])
    return [
        {
            "term_name": b["term_name"],
            "total_billed": str(b["total_billed"]),
            "total_paid": str(b["total_paid"]),
            "balance": str(b["total_billed"] - b["total_paid"]),
            "invoice_count": b["invoice_count"],
        }
        for b in ordered
    ]


def suggest_payment_plan(db: Session, guardian_user_id: str, student_name: str | None = None) -> list[dict]:
    """A preview only — mirrors payment_plan_service.recommend_payment_plan
    exactly, never persists anything (the assistant can't take actions on
    the parent's behalf, same rule as payments and linking a child). If
    they like it, they accept it for real via the 'Request a payment plan'
    button on the invoice in their portal."""
    student_ids = _resolve_student_ids(db, guardian_user_id, student_name)
    if not student_ids:
        return []

    rows = db.execute(
        select(Invoice, Student)
        .join(Student, Invoice.student_id == Student.id)
        .where(Invoice.student_id.in_(student_ids))
    ).all()

    result = []
    for invoice, student in rows:
        balance = invoice.total_amount - invoice.amount_paid
        if balance <= 0:
            continue
        recommendation = recommend_payment_plan(db, invoice.student_id, invoice.id)
        if not recommendation.installments:
            continue
        result.append(
            {
                "student_name": student.full_name,
                "invoice_due_date": invoice.due_date.date().isoformat(),
                "balance": str(balance),
                "rationale": recommendation.rationale,
                "installments": [
                    {"amount": str(i.amount), "due_date": i.due_date.date().isoformat()} for i in recommendation.installments
                ],
            }
        )
    return result

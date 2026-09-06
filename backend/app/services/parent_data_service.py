"""Read-only queries for the parent AI assistant — every function here
takes guardian_user_id (from the caller's own JWT) and resolves it through
student_guardians itself. None of these accept a student_id from outside,
mirroring the same rule parent.py's list_my_children enforces: the link
table is the only source of truth for what a parent can see, never a
client-supplied id — including one an LLM might be tricked into passing."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.student import SchoolClass, Student, StudentGuardian


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

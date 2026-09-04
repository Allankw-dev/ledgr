from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas.parent import ParentStudentView, ParentInvoiceView, ParentPaymentView
from app.models.student import Student, StudentGuardian
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.enums import GuardianLinkStatus, PaymentStatus


def get_my_children(db: Session, user_id: str) -> list[ParentStudentView]:
    """
    Returns only the students linked to the given parent user_id via
    student_guardians — this is the single source of truth for "what is
    this parent allowed to see" across the whole app. The parent portal
    page and the AI chatbot both call this SAME function rather than each
    writing their own version of this query, specifically so there is only
    one place this scoping logic can go wrong, not two.

    Filtering to APPROVED only is deliberate: a parent who self-registered
    and requested a link via admission number sees NOTHING for that child
    — not even a "pending" placeholder with real data — until a bursar has
    reviewed and approved the request. A bursar-initiated link (via the
    "Link parent" flow) is APPROVED immediately, since a bursar is already
    trusted and already looking at the real record.
    """
    links = db.execute(
        select(StudentGuardian).where(
            StudentGuardian.user_id == user_id,
            StudentGuardian.status == GuardianLinkStatus.APPROVED,
        )
    ).scalars().all()
    student_ids = [link.student_id for link in links]
    if not student_ids:
        return []

    students = db.execute(select(Student).where(Student.id.in_(student_ids))).scalars().all()

    results = []
    for student in students:
        invoices = db.execute(
            select(Invoice).where(Invoice.student_id == student.id).order_by(Invoice.due_date.desc())
        ).scalars().all()

        balance_due = sum((inv.total_amount - inv.amount_paid for inv in invoices), Decimal("0"))

        invoice_views = []
        for inv in invoices:
            payments = db.execute(
                select(Payment)
                .where(Payment.invoice_id == inv.id, Payment.status == PaymentStatus.CONFIRMED, Payment.amount > 0)
                .order_by(Payment.paid_at.desc())
            ).scalars().all()

            invoice_views.append(
                ParentInvoiceView(
                    id=inv.id,
                    total_amount=inv.total_amount,
                    amount_paid=inv.amount_paid,
                    due_date=inv.due_date,
                    status=inv.status.value,
                    payments=[
                        ParentPaymentView(id=p.id, amount=p.amount, method=p.method.value, paid_at=p.paid_at)
                        for p in payments
                    ],
                )
            )

        results.append(
            ParentStudentView(
                id=student.id,
                full_name=student.full_name,
                admission_number=student.admission_number,
                class_name=student.school_class.name if student.school_class else None,
                invoices=invoice_views,
                balance_due=balance_due,
            )
        )

    return results

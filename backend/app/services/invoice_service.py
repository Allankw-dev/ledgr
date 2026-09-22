from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.student import Student
from app.models.invoice import FeeStructure, Invoice, InvoiceItem
from app.models.payment import Payment
from app.models.enums import InvoiceStatus, PaymentStatus
from app.core import cache
from app.services import ml_data_service


def generate_invoice_for_student(
    db: Session, student_id: str, term_id: str, due_date: datetime, *, commit: bool = True
) -> Invoice:
    """
    Sums every applicable FeeStructure (class-specific + school-wide) for the
    term into one invoice. Idempotent: raises rather than silently creating
    a duplicate bill if one already exists for this student/term.
    """
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(404, "Student not found")

    existing = db.execute(
        select(Invoice).where(Invoice.student_id == student_id, Invoice.term_id == term_id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "An invoice already exists for this student and term")

    fee_structures = db.execute(
        select(FeeStructure).where(
            FeeStructure.term_id == term_id,
            FeeStructure.school_id == student.school_id,
            (FeeStructure.class_id == student.class_id) | (FeeStructure.class_id.is_(None)),
        )
    ).scalars().all()

    if not fee_structures:
        raise HTTPException(422, "No fee structure defined for this student's class/term yet")

    total_amount = sum((fs.amount for fs in fee_structures), Decimal("0"))

    invoice = Invoice(
        school_id=student.school_id,
        student_id=student_id,
        term_id=term_id,
        total_amount=total_amount,
        due_date=due_date,
        status=InvoiceStatus.ISSUED,
    )
    # The existence check above is only a friendly early exit. Two requests can
    # both pass it at the same instant; the unique index (student_id, term_id)
    # is what actually guarantees one bill. SAVEPOINT so the loser's failure
    # doesn't poison the caller's transaction (bulk-generate reuses the session).
    try:
        with db.begin_nested():
            db.add(invoice)
            db.flush()  # populate invoice.id before creating items
            for fs in fee_structures:
                db.add(InvoiceItem(invoice_id=invoice.id, fee_structure_id=fs.id, amount=fs.amount))
    except IntegrityError:
        raise HTTPException(409, "An invoice already exists for this student and term")

    if commit:
        db.commit()
        db.refresh(invoice)
        cache.bump(student.school_id, "fin")
    return invoice


def recalculate_invoice_status(db: Session, invoice_id: str, *, commit: bool = True) -> Invoice:
    """
    Recomputes amount_paid and status from CONFIRMED payments only. Called
    after every payment state change so status is always derived from the
    ledger, never hand-set — it can't drift out of sync with reality.

    Concurrency: the invoice row is locked (SELECT ... FOR UPDATE) before the
    ledger is totalled, so two payments landing on the same invoice at once
    are applied one after the other — neither can overwrite the other's total
    with a stale sum. Pass commit=False to make this part of the caller's
    transaction (payment row + invoice total then commit, or roll back, together).
    """
    invoice = db.execute(select(Invoice).where(Invoice.id == invoice_id).with_for_update()).scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    # Total in the database (index-only scan on ix_payments_invoice_status)
    # rather than loading every payment row into Python.
    amount_paid = db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.invoice_id == invoice_id, Payment.status == PaymentStatus.CONFIRMED
        )
    ).scalar_one()
    amount_paid = Decimal(amount_paid)

    if invoice.status == InvoiceStatus.CANCELLED:
        status = InvoiceStatus.CANCELLED  # a voided invoice stays void, whatever gets recorded against it
    elif amount_paid >= invoice.total_amount:
        status = InvoiceStatus.PAID
    elif amount_paid > 0:
        status = InvoiceStatus.PARTIALLY_PAID
    elif invoice.due_date < datetime.now(timezone.utc):
        status = InvoiceStatus.OVERDUE
    else:
        status = InvoiceStatus.ISSUED

    invoice.amount_paid = amount_paid
    invoice.status = status
    ml_data_service.log_invoice_outcome_if_resolved(db, invoice)
    if commit:
        db.commit()
        db.refresh(invoice)
        cache.bump(invoice.school_id, "fin")
    else:
        db.flush()
    return invoice

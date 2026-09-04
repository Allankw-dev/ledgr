from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.student import Student
from app.models.invoice import FeeStructure, Invoice, InvoiceItem
from app.models.payment import Payment
from app.models.enums import InvoiceStatus, PaymentStatus


def generate_invoice_for_student(db: Session, student_id: str, term_id: str, due_date: datetime) -> Invoice:
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
    db.add(invoice)
    db.flush()  # populate invoice.id before creating items

    for fs in fee_structures:
        db.add(InvoiceItem(invoice_id=invoice.id, fee_structure_id=fs.id, amount=fs.amount))

    db.commit()
    db.refresh(invoice)
    return invoice


def recalculate_invoice_status(db: Session, invoice_id: str) -> Invoice:
    """
    Recomputes amount_paid and status from CONFIRMED payments only. Called
    after every payment state change so status is always derived from the
    ledger, never hand-set — it can't drift out of sync with reality.
    """
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    confirmed = db.execute(
        select(Payment).where(Payment.invoice_id == invoice_id, Payment.status == PaymentStatus.CONFIRMED)
    ).scalars().all()

    amount_paid = sum((p.amount for p in confirmed), Decimal("0"))

    if amount_paid >= invoice.total_amount:
        status = InvoiceStatus.PAID
    elif amount_paid > 0:
        status = InvoiceStatus.PARTIALLY_PAID
    elif invoice.due_date < datetime.now(timezone.utc):
        status = InvoiceStatus.OVERDUE
    else:
        status = InvoiceStatus.ISSUED

    invoice.amount_paid = amount_paid
    invoice.status = status
    db.commit()
    db.refresh(invoice)
    return invoice

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


def generate_invoices_bulk(
    db: Session, school_id: str, students: list[Student], term_id: str, due_date: datetime, *, chunk_size: int = 500
) -> tuple[int, list[dict]]:
    """generate_invoice_for_student for MANY students, in a handful of database round trips.

    The one-at-a-time version costs ~5 round trips per student. Against a hosted database
    (~20 ms each) that is ~100 ms a student, so one class of 800 already overran the 60 s
    request limit and a whole school of 8,000 would have taken ~13 minutes. This loads the
    term's fee structures and the already-invoiced students ONCE, then inserts invoices and
    their line items a chunk at a time. Results are identical, student for student: same
    totals and items, same "already exists" / "no fee structure" skips (same messages).

    Returns (created, errors) where errors is [{"student_id", "error"}, ...] like before.
    Each chunk commits on its own, so a long run keeps the progress it made, and re-running
    simply skips the students already done."""
    errors: list[dict] = []

    def skip(student_id: str, status: int, detail: str) -> None:
        errors.append({"student_id": student_id, "error": str(HTTPException(status, detail))})

    fee_rows = db.execute(
        select(FeeStructure).where(FeeStructure.term_id == term_id, FeeStructure.school_id == school_id)
    ).scalars().all()
    school_wide = [fs for fs in fee_rows if fs.class_id is None]
    by_class: dict[str, list[FeeStructure]] = {}
    for fs in fee_rows:
        if fs.class_id is not None:
            by_class.setdefault(fs.class_id, []).append(fs)

    already: set[str] = set()
    student_ids = [s.id for s in students]
    for i in range(0, len(student_ids), 2000):
        already.update(
            db.execute(
                select(Invoice.student_id).where(Invoice.term_id == term_id, Invoice.student_id.in_(student_ids[i : i + 2000]))
            ).scalars().all()
        )

    pending: list[tuple[Student, list[FeeStructure]]] = []
    for student in students:
        if student.id in already:
            skip(student.id, 409, "An invoice already exists for this student and term")
            continue
        fees = [*by_class.get(student.class_id, []), *school_wide] if student.class_id else list(school_wide)
        if not fees:
            skip(student.id, 422, "No fee structure defined for this student's class/term yet")
            continue
        pending.append((student, fees))

    created = 0
    for i in range(0, len(pending), chunk_size):
        chunk = pending[i : i + chunk_size]
        try:
            with db.begin_nested():
                invoices = [
                    Invoice(
                        school_id=school_id,
                        student_id=student.id,
                        term_id=term_id,
                        total_amount=sum((fs.amount for fs in fees), Decimal("0")),
                        due_date=due_date,
                        status=InvoiceStatus.ISSUED,
                    )
                    for student, fees in chunk
                ]
                db.add_all(invoices)
                db.flush()
                db.add_all(
                    InvoiceItem(invoice_id=invoice.id, fee_structure_id=fs.id, amount=fs.amount)
                    for invoice, (_, fees) in zip(invoices, chunk)
                    for fs in fees
                )
                db.flush()
            db.commit()
            created += len(chunk)
        except IntegrityError:
            # Someone else generated some of these invoices a moment ago (the unique index on
            # student+term caught it). Redo this chunk one student at a time so every student is
            # still accounted for as created or skipped.
            db.rollback()
            for student, _ in chunk:
                try:
                    generate_invoice_for_student(db, student.id, term_id, due_date)
                    created += 1
                except HTTPException as exc:
                    skip(student.id, exc.status_code, exc.detail)
    if created:
        cache.bump(school_id, "fin")
    return created, errors


# Invoices money can still be collected against. DRAFT isn't issued yet, PAID has
# nothing left, CANCELLED is void.
OPEN_INVOICE_STATUSES = (InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE)


def student_open_invoices(db: Session, student_id: str, *, for_update: bool = False) -> list[Invoice]:
    """A student's collectable invoices, oldest due date first (id breaks ties so
    every caller locks them in the same order — two transactions locking the same
    set in different orders is how deadlocks happen)."""
    query = (
        select(Invoice)
        .where(Invoice.student_id == student_id, Invoice.status.in_(OPEN_INVOICE_STATUSES))
        .order_by(Invoice.due_date.asc(), Invoice.id.asc())
    )
    if for_update:
        query = query.with_for_update()
    return list(db.execute(query).scalars().all())


def student_open_balance(db: Session, student_id: str) -> Decimal:
    return sum(
        (max(inv.total_amount - inv.amount_paid, Decimal("0")) for inv in student_open_invoices(db, student_id)),
        Decimal("0"),
    )


def lock_invoice(db: Session, invoice_id: str) -> Invoice:
    """SELECT ... FOR UPDATE on the invoice. Call this BEFORE inserting a payment
    row that points at it: that INSERT takes a shared (FOR KEY SHARE) lock on the
    invoice through the foreign key, and two transactions that each hold a share
    lock and then ask for FOR UPDATE deadlock each other. Taking the exclusive
    lock first makes them queue up instead."""
    invoice = db.execute(select(Invoice).where(Invoice.id == invoice_id).with_for_update()).scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    return invoice


def recalculate_invoice_status(db: Session, invoice_id: str, *, commit: bool = True) -> Invoice:
    """
    Recomputes amount_paid and status from the payment ledger (CONFIRMED rows
    plus the REVERSED originals they cancel out — see below). Called
    after every payment state change so status is always derived from the
    ledger, never hand-set — it can't drift out of sync with reality.

    Concurrency: the invoice row is locked (SELECT ... FOR UPDATE) before the
    ledger is totalled, so two payments landing on the same invoice at once
    are applied one after the other — neither can overwrite the other's total
    with a stale sum. Pass commit=False to make this part of the caller's
    transaction (payment row + invoice total then commit, or roll back, together).
    """
    invoice = lock_invoice(db, invoice_id)

    # Sessions here run with autoflush=False, so a payment whose status the
    # caller just changed (e.g. PENDING -> CONFIRMED in the M-Pesa callback) is
    # invisible to the SUM below until it is flushed. Without this the invoice
    # silently keeps its old total.
    db.flush()

    # Total in the database (index-only scan on ix_payments_invoice_status)
    # rather than loading every payment row into Python.
    #
    # REVERSED originals count too: a reversal keeps the original row (status
    # REVERSED, +x) and adds a CONFIRMED correction row (-x). The pair nets to
    # zero. Counting only CONFIRMED would drop the +x and leave the -x, pushing
    # amount_paid negative and inflating what the parent owes.
    amount_paid = db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.invoice_id == invoice_id,
            Payment.status.in_([PaymentStatus.CONFIRMED, PaymentStatus.REVERSED]),
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

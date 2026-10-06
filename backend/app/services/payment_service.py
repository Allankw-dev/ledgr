from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import cache
from app.core.jobs import enqueue
from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.student import Student, StudentGuardian
from app.models.school import School, User
from app.models.enums import GuardianLinkStatus, PaymentMethod, PaymentStatus
from app.services.invoice_service import OPEN_INVOICE_STATUSES, lock_invoice, recalculate_invoice_status, student_open_balance, student_open_invoices
from app.services.audit_service import log_audit


def record_confirmed_payment(
    db: Session,
    school_id: str,
    student_id: str,
    amount: Decimal,
    method: PaymentMethod,
    invoice_id: str | None = None,
    reference_code: str | None = None,
    external_txn_id: str | None = None,
    actor_user_id: str | None = None,
    *,
    commit: bool = True,
) -> Payment:
    """
    Records a CONFIRMED payment and immediately reconciles the invoice.
    For M-Pesa, call this from the Daraja callback handler once the provider
    confirms the transaction — never mark CONFIRMED on the initial STK push.

    Transaction: the payment row, the audit log, the invoice recalculation
    (which locks the invoice — see recalculate_invoice_status) and the
    notification job all go in ONE transaction. Either the whole payment is
    recorded and its side effects are queued, or none of it is — there's no
    window where a payment exists but the invoice total hasn't caught up, or
    where a job was queued for a payment that then failed to save.
    """
    if amount <= 0:
        raise HTTPException(422, "Payment amount must be greater than zero")

    if invoice_id:
        # Exclusive invoice lock BEFORE the payment INSERT (see lock_invoice) —
        # otherwise two simultaneous payments on one invoice can deadlock.
        lock_invoice(db, invoice_id)

    payment = Payment(
        school_id=school_id,
        student_id=student_id,
        invoice_id=invoice_id,
        amount=amount,
        method=method,
        reference_code=reference_code,
        external_txn_id=external_txn_id,
        status=PaymentStatus.CONFIRMED,
        paid_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    db.flush()  # populate payment.id

    log_audit(
        db,
        school_id=school_id,
        action="PAYMENT_CONFIRMED",
        entity_type="Payment",
        entity_id=payment.id,
        user_id=actor_user_id,
        metadata={"amount": str(amount), "method": method.value},
    )

    if invoice_id:
        recalculate_invoice_status(db, invoice_id, commit=False)

    queue_payment_notification(db, payment, succeeded=True)

    if commit:
        db.commit()
        db.refresh(payment)
        cache.bump(school_id, "fin")
    return payment


def create_pending_mpesa_payment(
    db: Session,
    school_id: str,
    student_id: str,
    invoice_id: str | None,
    amount: Decimal,
    checkout_request_id: str,
) -> Payment:
    """
    Recorded the moment we send the STK push, BEFORE we know whether the
    parent actually completes it on their phone. Stays PENDING until the
    Daraja callback confirms or fails it — never counted toward the
    invoice's amount_paid while pending (recalculate_invoice_status only
    sums CONFIRMED payments).

    invoice_id=None means the parent paid toward the student's whole balance;
    the callback then splits the money across their open invoices (oldest first).
    """
    payment = Payment(
        school_id=school_id,
        student_id=student_id,
        invoice_id=invoice_id,
        amount=amount,
        method=PaymentMethod.MPESA,
        status=PaymentStatus.PENDING,
        external_txn_id=checkout_request_id,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    # No invoice/cache change yet — a PENDING payment isn't counted until the
    # callback confirms it (recalculate_invoice_status only sums CONFIRMED rows).
    return payment


def queue_payment_notification(
    db: Session,
    payment: Payment,
    succeeded: bool,
    *,
    amount: Decimal | None = None,
    remaining: Decimal | None = None,
) -> None:
    """Queues the parent's SMS/email as a durable job, enqueued in the SAME
    transaction as the payment (transactional outbox — see core/jobs.py). It
    only becomes visible to a worker once that transaction commits, so a
    payment that gets rolled back never leaves a stray notification behind,
    and a payment that DOES commit can never silently lose its notification
    to a crashed process (the old in-memory thread pool's failure mode).
    dedupe_key means a retried call (e.g. a duplicate M-Pesa callback) can't
    double-queue the same notification."""
    enqueue(
        db,
        school_id=payment.school_id,
        kind="notify_payment_result",
        payload={
            "payment_id": payment.id,
            "succeeded": succeeded,
            # A whole-balance payment is stored as several rows, so the message must
            # report the full amount and the student's overall balance, not one row's share.
            **({"amount": str(amount)} if amount is not None else {}),
            **({"remaining": str(remaining)} if remaining is not None else {}),
        },
        dedupe_key=f"pay-notify:{payment.id}:{succeeded}",
        urgent=True,  # ahead of any bulk broadcast waiting in the queue
    )


def _allocate_to_open_invoices(db: Session, payment: Payment) -> tuple[Decimal, list[dict]]:
    """Splits a CONFIRMED whole-balance payment across the student's open invoices,
    oldest due date first. The pending row becomes the first slice (so its receipt
    and id keep working); further slices are new CONFIRMED rows carrying the same
    M-Pesa receipt. Allocation happens HERE, at confirmation time, against the
    balances as they are now — a cash payment recorded between the STK push and
    the PIN entry can't cause an invoice to be overpaid.

    Anything that doesn't fit (invoices paid off in the meantime) is kept as an
    unallocated row with no invoice and flagged in the audit log for the bursar.
    Returns (total_amount, [{invoice_id, amount}, ...]); the caller recalculates
    the touched invoices.
    """
    total = payment.amount
    remaining = total
    slices: list[dict] = []

    for invoice in student_open_invoices(db, payment.student_id, for_update=True):
        if remaining <= 0:
            break
        owed = invoice.total_amount - invoice.amount_paid
        if owed <= 0:
            continue
        take = min(owed, remaining)
        if not slices:
            payment.invoice_id = invoice.id
            payment.amount = take
        else:
            db.add(
                Payment(
                    school_id=payment.school_id,
                    student_id=payment.student_id,
                    invoice_id=invoice.id,
                    amount=take,
                    method=PaymentMethod.MPESA,
                    status=PaymentStatus.CONFIRMED,
                    reference_code=payment.reference_code,
                    external_txn_id=payment.external_txn_id,
                    paid_at=payment.paid_at,
                    notes="Part of one M-Pesa payment applied across several invoices",
                )
            )
        slices.append({"invoice_id": invoice.id, "amount": str(take)})
        remaining -= take

    if remaining > 0:
        if slices:
            db.add(
                Payment(
                    school_id=payment.school_id,
                    student_id=payment.student_id,
                    invoice_id=None,
                    amount=remaining,
                    method=PaymentMethod.MPESA,
                    status=PaymentStatus.CONFIRMED,
                    reference_code=payment.reference_code,
                    external_txn_id=payment.external_txn_id,
                    paid_at=payment.paid_at,
                    notes="Unallocated: the open invoices were cleared before this M-Pesa payment arrived",
                )
            )
        # (if nothing was open at all the pending row itself stays, unallocated)
        log_audit(
            db,
            school_id=payment.school_id,
            action="MPESA_PAYMENT_UNALLOCATED",
            entity_type="Payment",
            entity_id=payment.id,
            metadata={"unallocated": str(remaining), "allocated": slices},
        )
    db.flush()
    return total, slices


def resolve_mpesa_callback(
    db: Session,
    checkout_request_id: str,
    result_code: int,
    mpesa_receipt_number: str | None,
    paid_amount: Decimal | int | float | str | None = None,
) -> Payment | None:
    """
    Called from the (public, unauthenticated) Daraja callback endpoint.
    Finds the PENDING payment created by create_pending_mpesa_payment via
    its CheckoutRequestID and resolves it to CONFIRMED or FAILED depending
    on Safaricom's result code. Returns None if no matching pending payment
    is found (e.g. a replayed or malformed callback) — callers should treat
    that as a no-op, not an error, since Safaricom does retry callbacks.
    """
    # FOR UPDATE serializes concurrent duplicate callbacks (Safaricom retries):
    # the second one waits for the first to commit, then no longer matches
    # status == PENDING and becomes a no-op — instead of both reading PENDING
    # at the same time and both confirming the payment / texting the parent.
    payment = db.execute(
        select(Payment)
        .where(
            Payment.external_txn_id == checkout_request_id,
            Payment.status == PaymentStatus.PENDING,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if not payment:
        return None

    # Never confirm money we can't account for: if Safaricom reports a
    # different amount than we asked for, leave the payment PENDING and flag
    # it for a human instead of marking the invoice paid.
    if result_code == 0 and paid_amount is not None:
        if Decimal(str(paid_amount)) != Decimal(str(payment.amount)):
            log_audit(
                db,
                school_id=payment.school_id,
                action="MPESA_CALLBACK_AMOUNT_MISMATCH",
                entity_type="Payment",
                entity_id=payment.id,
                metadata={"expected": str(payment.amount), "reported": str(paid_amount)},
            )
            db.commit()
            return None

    # Everything below is one transaction: the payment's new status, the
    # invoice recalculation (locked — see recalculate_invoice_status), the
    # audit row and the notification job either all land together or none do.
    if result_code == 0:
        payment.status = PaymentStatus.CONFIRMED
        payment.paid_at = datetime.now(timezone.utc)
        payment.reference_code = mpesa_receipt_number

        notify_amount = notify_remaining = None
        slices: list[dict] = []
        if payment.invoice_id:
            recalculate_invoice_status(db, payment.invoice_id, commit=False)
        else:
            notify_amount, slices = _allocate_to_open_invoices(db, payment)
            for part in slices:
                recalculate_invoice_status(db, part["invoice_id"], commit=False)
            notify_remaining = student_open_balance(db, payment.student_id)

        log_audit(
            db,
            school_id=payment.school_id,
            action="MPESA_PAYMENT_CONFIRMED",
            entity_type="Payment",
            entity_id=payment.id,
            metadata={
                "checkout_request_id": checkout_request_id,
                "mpesa_receipt": mpesa_receipt_number,
                **({"allocation": slices} if slices else {}),
            },
        )
        queue_payment_notification(db, payment, succeeded=True, amount=notify_amount, remaining=notify_remaining)
        db.commit()
        cache.bump(payment.school_id, "fin")
    else:
        payment.status = PaymentStatus.FAILED

        log_audit(
            db,
            school_id=payment.school_id,
            action="MPESA_PAYMENT_FAILED",
            entity_type="Payment",
            entity_id=payment.id,
            metadata={"checkout_request_id": checkout_request_id, "result_code": result_code},
        )
        queue_payment_notification(db, payment, succeeded=False)
        db.commit()

    db.refresh(payment)
    return payment


def reverse_payment(
    db: Session, school_id: str, payment_id: str, reason: str, actor_user_id: str | None = None
) -> Payment:
    """
    Reverses a payment via a linked correction row rather than editing or
    deleting the original — the ledger always shows exactly what happened.

    school_id is required and part of the lookup, so a payment from another school is
    simply "not found" — this must not depend on Row-Level Security being switched on.
    """
    # Locked so two clicks (or a click plus a retry) can't both pass the
    # "still CONFIRMED" check and reverse the same payment twice.
    original = db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.school_id == school_id).with_for_update()
    ).scalar_one_or_none()
    if not original:
        raise HTTPException(404, "Payment not found")
    if original.status != PaymentStatus.CONFIRMED:
        raise HTTPException(422, "Only confirmed payments can be reversed")

    if original.invoice_id:
        lock_invoice(db, original.invoice_id)  # before the INSERT below, same reason as record_confirmed_payment

    reversal = Payment(
        school_id=original.school_id,
        student_id=original.student_id,
        invoice_id=original.invoice_id,
        amount=-original.amount,
        method=original.method,
        status=PaymentStatus.CONFIRMED,
        reversal_of_id=original.id,
        notes=reason,
        paid_at=datetime.now(timezone.utc),
    )
    original.status = PaymentStatus.REVERSED
    db.add(reversal)
    db.flush()

    log_audit(
        db,
        school_id=original.school_id,
        action="PAYMENT_REVERSED",
        entity_type="Payment",
        entity_id=original.id,
        user_id=actor_user_id,
        metadata={"reason": reason, "reversal_id": reversal.id},
    )

    if original.invoice_id:
        recalculate_invoice_status(db, original.invoice_id, commit=False)

    db.commit()
    db.refresh(reversal)
    cache.bump(original.school_id, "fin")
    return reversal


# --- Unallocated money -------------------------------------------------------


def _unallocated_filter(school_id: str):
    """CONFIRMED, positive, not a reversal row, attached to no invoice."""
    return (
        Payment.school_id == school_id,
        Payment.invoice_id.is_(None),
        Payment.status == PaymentStatus.CONFIRMED,
        Payment.amount > 0,
        Payment.reversal_of_id.is_(None),
    )


def list_unallocated_payments(db: Session, school_id: str) -> list[dict]:
    """Every payment waiting for a bursar's decision, with the invoices it could be
    applied to. Oldest first, so nothing sits forgotten at the bottom."""
    from app.models.invoice import Invoice
    from app.models.student import Student, Term

    rows = db.execute(
        select(Payment, Student)
        .join(Student, Student.id == Payment.student_id)
        .where(*_unallocated_filter(school_id))
        .order_by(Payment.paid_at.asc().nulls_last(), Payment.created_at.asc())
    ).all()
    if not rows:
        return []

    student_ids = {payment.student_id for payment, _ in rows}
    invoice_rows = db.execute(
        select(Invoice, Term.name)
        .join(Term, Term.id == Invoice.term_id, isouter=True)
        .where(Invoice.student_id.in_(student_ids), Invoice.status.in_(OPEN_INVOICE_STATUSES))
        .order_by(Invoice.due_date.asc(), Invoice.id.asc())
    ).all()
    open_by_student: dict[str, list[dict]] = {}
    for invoice, term_name in invoice_rows:
        balance = invoice.total_amount - invoice.amount_paid
        if balance <= 0:
            continue
        open_by_student.setdefault(invoice.student_id, []).append(
            {"id": invoice.id, "label": term_name or "Invoice", "due_date": invoice.due_date, "balance": balance}
        )

    return [
        {
            "id": payment.id,
            "student_id": student.id,
            "student_name": student.full_name,
            "admission_number": student.admission_number,
            "amount": payment.amount,
            "method": payment.method.value,
            "reference_code": payment.reference_code,
            "paid_at": payment.paid_at,
            "notes": payment.notes,
            "open_invoices": open_by_student.get(student.id, []),
        }
        for payment, student in rows
    ]


def apply_unallocated_payment(
    db: Session, school_id: str, payment_id: str, invoice_id: str, actor_user_id: str | None = None
) -> Payment:
    """Puts an unallocated payment against one of the same student's open invoices.

    The ledger stays append-only: the original row is marked REVERSED and cancelled by
    a correction row, and the money is re-recorded as new CONFIRMED rows — one on the
    invoice (up to what it still owes) and, if there is more than that, one still
    unallocated. All of it in one transaction. No "payment received" message is sent:
    the parent was already told when the money arrived."""
    from app.models.invoice import Invoice

    original = db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.school_id == school_id).with_for_update()
    ).scalar_one_or_none()
    if not original:
        raise HTTPException(404, "Payment not found")
    if (
        original.invoice_id is not None
        or original.status != PaymentStatus.CONFIRMED
        or original.amount <= 0
        or original.reversal_of_id is not None
    ):
        raise HTTPException(422, "This payment is not waiting to be allocated")

    invoice = lock_invoice(db, invoice_id)
    if invoice.school_id != school_id:
        raise HTTPException(404, "Invoice not found")
    if invoice.student_id != original.student_id:
        raise HTTPException(422, "That invoice belongs to a different student")
    balance = invoice.total_amount - invoice.amount_paid
    if invoice.status not in OPEN_INVOICE_STATUSES or balance <= 0:
        raise HTTPException(422, "That invoice has nothing left to pay")

    take = min(original.amount, balance)
    remainder = original.amount - take
    now = datetime.now(timezone.utc)
    shared = dict(
        school_id=original.school_id,
        student_id=original.student_id,
        method=original.method,
        status=PaymentStatus.CONFIRMED,
        reference_code=original.reference_code,
        external_txn_id=original.external_txn_id,
    )

    original.status = PaymentStatus.REVERSED
    db.add(Payment(**{**shared, "invoice_id": None, "amount": -original.amount}, reversal_of_id=original.id,
                   notes="Allocated to an invoice", paid_at=now))
    applied = Payment(**{**shared, "invoice_id": invoice.id, "amount": take},
                      paid_at=original.paid_at or now, notes="Applied from an unallocated payment")
    db.add(applied)
    if remainder > 0:
        db.add(Payment(**{**shared, "invoice_id": None, "amount": remainder},
                       paid_at=original.paid_at or now, notes="Unallocated remainder"))
    db.flush()

    log_audit(
        db,
        school_id=school_id,
        action="PAYMENT_ALLOCATED",
        entity_type="Payment",
        entity_id=original.id,
        user_id=actor_user_id,
        metadata={"invoice_id": invoice.id, "applied": str(take), "remainder": str(remainder), "new_payment_id": applied.id},
    )
    recalculate_invoice_status(db, invoice.id, commit=False)
    db.commit()
    db.refresh(applied)
    cache.bump(school_id, "fin")
    return applied

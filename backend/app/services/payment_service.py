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
from app.services.invoice_service import recalculate_invoice_status
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
    invoice_id: str,
    amount: Decimal,
    checkout_request_id: str,
) -> Payment:
    """
    Recorded the moment we send the STK push, BEFORE we know whether the
    parent actually completes it on their phone. Stays PENDING until the
    Daraja callback confirms or fails it — never counted toward the
    invoice's amount_paid while pending (recalculate_invoice_status only
    sums CONFIRMED payments).
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


def queue_payment_notification(db: Session, payment: Payment, succeeded: bool) -> None:
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
        payload={"payment_id": payment.id, "succeeded": succeeded},
        dedupe_key=f"pay-notify:{payment.id}:{succeeded}",
    )


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

        if payment.invoice_id:
            recalculate_invoice_status(db, payment.invoice_id, commit=False)

        log_audit(
            db,
            school_id=payment.school_id,
            action="MPESA_PAYMENT_CONFIRMED",
            entity_type="Payment",
            entity_id=payment.id,
            metadata={"checkout_request_id": checkout_request_id, "mpesa_receipt": mpesa_receipt_number},
        )
        queue_payment_notification(db, payment, succeeded=True)
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


def reverse_payment(db: Session, payment_id: str, reason: str, actor_user_id: str | None = None) -> Payment:
    """
    Reverses a payment via a linked correction row rather than editing or
    deleting the original — the ledger always shows exactly what happened.
    """
    # Locked so two clicks (or a click plus a retry) can't both pass the
    # "still CONFIRMED" check and reverse the same payment twice.
    original = db.execute(select(Payment).where(Payment.id == payment_id).with_for_update()).scalar_one_or_none()
    if not original:
        raise HTTPException(404, "Payment not found")
    if original.status != PaymentStatus.CONFIRMED:
        raise HTTPException(422, "Only confirmed payments can be reversed")

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

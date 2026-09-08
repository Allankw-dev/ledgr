from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.student import Student, StudentGuardian
from app.models.school import School, User
from app.models.enums import GuardianLinkStatus, PaymentMethod, PaymentStatus
from app.services.invoice_service import recalculate_invoice_status
from app.services.audit_service import log_audit
from app.services.notification_service import (
    compose_payment_confirmation,
    compose_payment_failed,
    send_message_to_guardian,
)


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
) -> Payment:
    """
    Records a CONFIRMED payment and immediately reconciles the invoice.
    For M-Pesa, call this from the Daraja callback handler once the provider
    confirms the transaction — never mark CONFIRMED on the initial STK push.
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
    db.flush()

    log_audit(
        db,
        school_id=school_id,
        action="PAYMENT_CONFIRMED",
        entity_type="Payment",
        entity_id=payment.id,
        user_id=actor_user_id,
        metadata={"amount": str(amount), "method": method.value},
    )
    db.commit()

    if invoice_id:
        recalculate_invoice_status(db, invoice_id)

    _notify_guardians_of_payment_result(db, payment, succeeded=True)

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
    return payment


def _notify_guardians_of_payment_result(db: Session, payment: Payment, succeeded: bool) -> None:
    """
    Best-effort — a notification failure here must never break the M-Pesa
    callback flow (Safaricom needs a clean ack regardless), so every
    failure mode short-circuits quietly rather than raising. This is what
    replaces the old behavior of a parent only finding out a payment
    worked by refreshing the dashboard and watching the balance change.
    """
    try:
        student = db.get(Student, payment.student_id)
        school = db.get(School, payment.school_id)
        if not student or not school:
            return

        guardians = db.execute(
            select(StudentGuardian).where(
                StudentGuardian.student_id == student.id,
                StudentGuardian.status == GuardianLinkStatus.APPROVED,
            )
        ).scalars().all()
        if not guardians:
            return

        if succeeded:
            remaining_balance = Decimal("0")
            if payment.invoice_id:
                invoice = db.get(Invoice, payment.invoice_id)
                if invoice:
                    remaining_balance = invoice.total_amount - invoice.amount_paid
            subject, body, sms_text = compose_payment_confirmation(
                student_name=student.full_name,
                school_name=school.name,
                amount=payment.amount,
                currency=school.currency,
                method=payment.method.value,
                remaining_balance=remaining_balance,
            )
        else:
            subject, body, sms_text = compose_payment_failed(
                student_name=student.full_name,
                school_name=school.name,
                amount=payment.amount,
                currency=school.currency,
            )

        for link in guardians:
            guardian = db.get(User, link.user_id)
            if guardian:
                send_message_to_guardian(guardian.email, guardian.phone, subject, body, sms_text)
    except Exception:
        # Deliberately swallowed — see docstring. The payment itself is
        # already resolved and committed by the time this runs.
        pass


def resolve_mpesa_callback(
    db: Session,
    checkout_request_id: str,
    result_code: int,
    mpesa_receipt_number: str | None,
) -> Payment | None:
    """
    Called from the (public, unauthenticated) Daraja callback endpoint.
    Finds the PENDING payment created by create_pending_mpesa_payment via
    its CheckoutRequestID and resolves it to CONFIRMED or FAILED depending
    on Safaricom's result code. Returns None if no matching pending payment
    is found (e.g. a replayed or malformed callback) — callers should treat
    that as a no-op, not an error, since Safaricom does retry callbacks.
    """
    payment = db.execute(
        select(Payment).where(
            Payment.external_txn_id == checkout_request_id,
            Payment.status == PaymentStatus.PENDING,
        )
    ).scalar_one_or_none()

    if not payment:
        return None

    if result_code == 0:
        payment.status = PaymentStatus.CONFIRMED
        payment.paid_at = datetime.now(timezone.utc)
        payment.reference_code = mpesa_receipt_number
        db.commit()

        if payment.invoice_id:
            recalculate_invoice_status(db, payment.invoice_id)

        log_audit(
            db,
            school_id=payment.school_id,
            action="MPESA_PAYMENT_CONFIRMED",
            entity_type="Payment",
            entity_id=payment.id,
            metadata={"checkout_request_id": checkout_request_id, "mpesa_receipt": mpesa_receipt_number},
        )
        db.commit()
        _notify_guardians_of_payment_result(db, payment, succeeded=True)
    else:
        payment.status = PaymentStatus.FAILED
        db.commit()

        log_audit(
            db,
            school_id=payment.school_id,
            action="MPESA_PAYMENT_FAILED",
            entity_type="Payment",
            entity_id=payment.id,
            metadata={"checkout_request_id": checkout_request_id, "result_code": result_code},
        )
        db.commit()
        _notify_guardians_of_payment_result(db, payment, succeeded=False)

    return payment


def reverse_payment(db: Session, payment_id: str, reason: str, actor_user_id: str | None = None) -> Payment:
    """
    Reverses a payment via a linked correction row rather than editing or
    deleting the original — the ledger always shows exactly what happened.
    """
    original = db.get(Payment, payment_id)
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
    db.commit()
    db.refresh(reversal)

    if original.invoice_id:
        recalculate_invoice_status(db, original.invoice_id)

    return reversal

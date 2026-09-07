from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mpesa_transaction import MpesaTransaction
from app.models.student import Student
from app.models.invoice import Invoice
from app.models.enums import MpesaTransactionStatus, PaymentMethod
from app.services.payment_service import record_confirmed_payment
from app.services.audit_service import log_audit
from app.schemas.mpesa import C2BPayload


def _parse_trans_time(raw: str | None) -> datetime | None:
    # Safaricom sends "20260907143012" (YYYYMMDDHHMMSS), not ISO — and this
    # field has been flaky in their docs before, so fail soft rather than
    # ever letting a formatting quirk drop a real transaction.
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def record_c2b_transaction(db: Session, payload: C2BPayload) -> MpesaTransaction:
    """
    Called from the public C2B confirmation endpoint. Idempotent on
    trans_id — Safaricom can and does retry confirmations, and re-processing
    one as a second payment would double-count real money received.

    Attempts to auto-match by BillRefNumber == a student's admission_number.
    admission_number is only unique per school (not globally), so exactly
    one match auto-confirms the payment; zero or multiple matches are left
    UNMATCHED for a bursar to resolve manually via /reconciliation/match —
    guessing wrong here is worse than asking a human.
    """
    existing = db.execute(
        select(MpesaTransaction).where(MpesaTransaction.trans_id == payload.TransID)
    ).scalar_one_or_none()
    if existing:
        return existing

    try:
        amount = Decimal(payload.TransAmount)
    except (InvalidOperation, TypeError):
        amount = Decimal("0")

    payer_name = " ".join(
        part for part in [payload.FirstName, payload.MiddleName, payload.LastName] if part
    ) or None

    txn = MpesaTransaction(
        trans_id=payload.TransID,
        trans_time=_parse_trans_time(payload.TransTime),
        amount=amount,
        bill_ref_number=(payload.BillRefNumber or "").strip() or None,
        msisdn=payload.MSISDN,
        payer_name=payer_name,
    )
    db.add(txn)
    db.flush()

    if txn.bill_ref_number and amount > 0:
        candidates = db.execute(
            select(Student).where(Student.admission_number == txn.bill_ref_number, Student.is_active.is_(True))
        ).scalars().all()

        if len(candidates) == 1:
            student = candidates[0]
            open_invoice = db.execute(
                select(Invoice)
                .where(
                    Invoice.student_id == student.id,
                    Invoice.status.in_(["ISSUED", "PARTIALLY_PAID", "OVERDUE"]),
                )
                .order_by(Invoice.due_date.asc())
            ).scalars().first()

            payment = record_confirmed_payment(
                db,
                school_id=student.school_id,
                student_id=student.id,
                amount=amount,
                method=PaymentMethod.MPESA,
                invoice_id=open_invoice.id if open_invoice else None,
                reference_code=txn.trans_id,
                external_txn_id=txn.trans_id,
            )

            txn.status = MpesaTransactionStatus.MATCHED
            txn.school_id = student.school_id
            txn.matched_student_id = student.id
            txn.matched_payment_id = payment.id
            txn.resolved_at = datetime.now(timezone.utc)

            log_audit(
                db,
                school_id=student.school_id,
                action="MPESA_C2B_AUTO_MATCHED",
                entity_type="MpesaTransaction",
                entity_id=txn.id,
                metadata={"trans_id": txn.trans_id, "student_id": student.id, "amount": str(amount)},
            )

    db.commit()
    db.refresh(txn)
    return txn


def find_unmatched_transaction(db: Session, trans_id: str) -> MpesaTransaction:
    """
    A bursar looks this up using the M-Pesa code the parent read out to
    them — a targeted lookup by an ID they already possess, not a listing,
    so it doesn't expose other schools' transactions. Only UNMATCHED
    transactions are returned; anything already MATCHED or IGNORED has
    nothing left for a bursar to act on.
    """
    txn = db.execute(
        select(MpesaTransaction).where(MpesaTransaction.trans_id == trans_id.strip())
    ).scalar_one_or_none()
    if not txn or txn.status != MpesaTransactionStatus.UNMATCHED:
        raise HTTPException(404, "No unmatched transaction found with that M-Pesa code")
    return txn


def match_transaction_to_invoice(
    db: Session,
    transaction_id: str,
    invoice_id: str,
    school_id: str,
    actor_user_id: str,
) -> MpesaTransaction:
    """
    Manual reconciliation: a bursar picks the invoice an UNMATCHED
    transaction actually belongs to (e.g. the parent typed a phone number
    instead of an admission number). invoice_id is resolved through the
    caller's own school_scope, so a bursar can only attach a stray
    transaction to an invoice in their own school.
    """
    txn = db.get(MpesaTransaction, transaction_id)
    if not txn or txn.status != MpesaTransactionStatus.UNMATCHED:
        raise HTTPException(404, "No unmatched transaction found")

    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.school_id == school_id)
    ).scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    payment = record_confirmed_payment(
        db,
        school_id=school_id,
        student_id=invoice.student_id,
        amount=txn.amount,
        method=PaymentMethod.MPESA,
        invoice_id=invoice.id,
        reference_code=txn.trans_id,
        external_txn_id=txn.trans_id,
        actor_user_id=actor_user_id,
    )

    txn.status = MpesaTransactionStatus.MATCHED
    txn.school_id = school_id
    txn.matched_student_id = invoice.student_id
    txn.matched_payment_id = payment.id
    txn.resolved_by_user_id = actor_user_id
    txn.resolved_at = datetime.now(timezone.utc)

    log_audit(
        db,
        school_id=school_id,
        action="MPESA_C2B_MANUALLY_MATCHED",
        entity_type="MpesaTransaction",
        entity_id=txn.id,
        user_id=actor_user_id,
        metadata={"trans_id": txn.trans_id, "invoice_id": invoice.id, "amount": str(txn.amount)},
    )
    db.commit()
    db.refresh(txn)
    return txn

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_school_scope, require_roles, get_current_user, CurrentUser
from app.schemas.payment import RecordPaymentRequest, ReversePaymentRequest, PaymentResponse
from app.schemas.anomaly import PaymentAnomalyResponse
from app.services.payment_service import record_confirmed_payment, reverse_payment
from app.services.anomaly_detection import scan_recent_anomalies

router = APIRouter(
    prefix="/api/payments",
    tags=["payments"],
    dependencies=[Depends(require_roles("SCHOOL_ADMIN", "BURSAR"))],
)


@router.post("", response_model=PaymentResponse, status_code=201)
def record_manual_payment(
    data: RecordPaymentRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Manual entry (cash/bank/cheque recorded by a bursar). M-Pesa payments
    go through the separate Daraja webhook handler instead, since those
    must only be confirmed once the provider callback arrives.
    """
    return record_confirmed_payment(
        db,
        school_id=school_id,
        student_id=data.student_id,
        amount=data.amount,
        method=data.method,
        invoice_id=data.invoice_id,
        reference_code=data.reference_code,
        actor_user_id=user.user_id,
    )


@router.post("/{payment_id}/reverse", response_model=PaymentResponse, status_code=201)
def reverse_payment_endpoint(
    payment_id: str,
    data: ReversePaymentRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    return reverse_payment(db, payment_id, data.reason, user.user_id)


@router.get("/anomalies", response_model=list[PaymentAnomalyResponse])
def get_flagged_payments(
    days: int = 30,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
):
    """Scans recent confirmed payments for this school and returns any
    that were flagged by at least one anomaly rule, for bursar review."""
    anomalies = scan_recent_anomalies(db, school_id, days=days)
    return [
        PaymentAnomalyResponse(
            payment_id=a.payment_id,
            student_id=a.student_id,
            amount=a.amount,
            paid_at=a.paid_at,
            reasons=a.reasons,
            severity=a.severity,
        )
        for a in anomalies
    ]

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, CurrentUser
from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.student import Student, StudentGuardian
from app.models.school import School
from app.models.enums import GuardianLinkStatus, PaymentStatus
from app.services.receipt_service import generate_receipt_pdf

router = APIRouter(prefix="/api/payments", tags=["receipts"], dependencies=[Depends(get_current_user)])


@router.get("/{payment_id}/receipt")
def download_receipt(
    payment_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Deliberately NOT restricted to bursar/admin like the rest of the
    payments router — a parent needs to be able to download a receipt for
    their own child's payment too. Authorization is checked explicitly
    below instead: bursars/admins can access any payment in their school,
    a parent only one tied to a student they're APPROVED-linked to.
    """
    payment = db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.school_id == school_id)
    ).scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")

    if payment.status != PaymentStatus.CONFIRMED:
        raise HTTPException(422, "Receipts are only available for confirmed payments")

    if user.role == "PARENT":
        link = db.execute(
            select(StudentGuardian).where(
                StudentGuardian.student_id == payment.student_id,
                StudentGuardian.user_id == user.user_id,
                StudentGuardian.status == GuardianLinkStatus.APPROVED,
            )
        ).scalar_one_or_none()
        if not link:
            raise HTTPException(403, "You don't have access to this receipt")
    elif user.role not in ("SCHOOL_ADMIN", "BURSAR", "SUPER_ADMIN"):
        raise HTTPException(403, "Not authorized")

    student = db.get(Student, payment.student_id)
    school = db.get(School, school_id)
    if not student or not school:
        raise HTTPException(404, "Related record not found")

    invoice_total = None
    invoice_balance_after = None
    if payment.invoice_id:
        invoice = db.get(Invoice, payment.invoice_id)
        if invoice:
            invoice_total = invoice.total_amount
            invoice_balance_after = invoice.total_amount - invoice.amount_paid

    pdf_bytes = generate_receipt_pdf(
        receipt_number=f"RCP-{payment.id[:8].upper()}",
        school_name=school.name,
        student_name=student.full_name,
        admission_number=student.admission_number,
        amount=payment.amount,
        currency=school.currency,
        method=payment.method.value,
        reference_code=payment.reference_code,
        paid_at=payment.paid_at,
        invoice_total=invoice_total,
        invoice_balance_after=invoice_balance_after,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="receipt-{payment.id[:8]}.pdf"'},
    )

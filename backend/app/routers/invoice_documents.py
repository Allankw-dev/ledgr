"""
Invoice documents and payment plans — deliberately a separate router from
routers/invoices.py, which gates its entire prefix to SCHOOL_ADMIN/BURSAR
only. A parent needs access to their own child's invoice (PDF, payment
plan) too, so this follows the same pattern as receipts.py and the
/students/{id}/statement endpoint: no blanket role dependency, explicit
authorization check inside each handler instead.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, CurrentUser
from app.models.invoice import Invoice, InvoiceItem, FeeStructure
from app.models.student import Student, SchoolClass, StudentGuardian, Term
from app.models.school import School
from app.models.enums import GuardianLinkStatus
from app.services.invoice_pdf_service import generate_invoice_pdf
from app.services.payment_plan_service import create_payment_plan, cancel_payment_plan, get_active_plan, get_installment_progress
from app.schemas.payment_plan import TrackedPaymentPlan, TrackedInstallment

router = APIRouter(prefix="/api/invoices", tags=["invoices"], dependencies=[Depends(get_current_user)])


def _get_authorized_invoice(db: Session, invoice_id: str, school_id: str, user: CurrentUser) -> Invoice:
    """Shared by every endpoint in this router: fetch the invoice scoped to
    this school, then confirm the caller may see it — either an approved
    guardian of the student it belongs to, or school staff."""
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.school_id == school_id)
    ).scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    if user.role == "PARENT":
        link = db.execute(
            select(StudentGuardian).where(
                StudentGuardian.student_id == invoice.student_id,
                StudentGuardian.user_id == user.user_id,
                StudentGuardian.status == GuardianLinkStatus.APPROVED,
            )
        ).scalar_one_or_none()
        if not link:
            raise HTTPException(403, "You don't have access to this invoice")
    elif user.role not in ("SCHOOL_ADMIN", "BURSAR", "SUPER_ADMIN"):
        raise HTTPException(403, "Not authorized")

    return invoice


@router.get("/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    invoice = _get_authorized_invoice(db, invoice_id, school_id, user)

    student = db.get(Student, invoice.student_id)
    school = db.get(School, school_id)
    term = db.get(Term, invoice.term_id)
    if not student or not school or not term:
        raise HTTPException(404, "Related record not found")

    school_class = db.get(SchoolClass, student.class_id) if student.class_id else None

    item_rows = db.execute(
        select(InvoiceItem, FeeStructure)
        .join(FeeStructure, InvoiceItem.fee_structure_id == FeeStructure.id)
        .where(InvoiceItem.invoice_id == invoice.id)
    ).all()

    pdf_bytes = generate_invoice_pdf(
        invoice_number=f"INV-{invoice.id[:8].upper()}",
        school_name=school.name,
        student_name=student.full_name,
        admission_number=student.admission_number,
        class_name=school_class.name if school_class else None,
        term_name=term.name,
        currency=school.currency,
        due_date=invoice.due_date,
        status=invoice.status.value,
        total_amount=invoice.total_amount,
        amount_paid=invoice.amount_paid,
        items=[
            {"name": fee_structure.name, "category": fee_structure.category.value, "amount": item.amount}
            for item, fee_structure in item_rows
        ],
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="invoice-{invoice.id[:8]}.pdf"'},
    )


def _serialize_plan(db: Session, plan) -> TrackedPaymentPlan:
    progress = get_installment_progress(db, plan)
    return TrackedPaymentPlan(
        id=plan.id,
        status=plan.status.value,
        rationale=plan.rationale,
        installments=[
            TrackedInstallment(sequence=p.sequence, amount=p.amount, due_date=p.due_date, paid=p.paid) for p in progress
        ],
    )


@router.get("/{invoice_id}/payment-plan/active", response_model=TrackedPaymentPlan | None)
def get_active_payment_plan(
    invoice_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """The plan a parent (or staff) already accepted for this invoice, with
    live paid/pending status per installment — distinct from the staff-only
    GET /{invoice_id}/payment-plan, which only ever returns a fresh,
    unsaved recommendation."""
    invoice = _get_authorized_invoice(db, invoice_id, school_id, user)
    plan = get_active_plan(db, invoice.id)
    if not plan:
        return None
    return _serialize_plan(db, plan)


@router.post("/{invoice_id}/payment-plan/accept", response_model=TrackedPaymentPlan)
def accept_payment_plan(
    invoice_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Either the parent themselves or a bursar can accept a recommended
    schedule on the family's behalf — a bursar offering a plan during a
    phone call is just as legitimate as a parent doing it from the portal."""
    invoice = _get_authorized_invoice(db, invoice_id, school_id, user)
    plan = create_payment_plan(db, invoice.id, actor_user_id=user.user_id)
    return _serialize_plan(db, plan)


@router.post("/{invoice_id}/payment-plan/cancel", response_model=TrackedPaymentPlan)
def cancel_active_payment_plan(
    invoice_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    invoice = _get_authorized_invoice(db, invoice_id, school_id, user)
    plan = get_active_plan(db, invoice.id)
    if not plan:
        raise HTTPException(404, "No active payment plan for this invoice")
    plan = cancel_payment_plan(db, plan)
    return _serialize_plan(db, plan)

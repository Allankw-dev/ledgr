from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_school_scope, require_roles
from app.schemas.invoice import GenerateInvoiceRequest, BulkGenerateRequest, BulkGenerateResult, InvoiceResponse, InvoiceListItem
from app.schemas.pagination import Page, PageMeta
from app.schemas.risk import RiskAssessmentResponse, RiskFactorsResponse
from app.schemas.payment_plan import PaymentPlanResponse, InstallmentResponse
from app.schemas.payment import PaymentResponse
from app.schemas.guardian_request import SendReminderResponse, ReminderRecipientResult
from app.models.student import Student, SchoolClass, StudentGuardian
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.school import School, User
from app.models.enums import PaymentStatus, GuardianLinkStatus
from app.services.invoice_service import generate_invoice_for_student
from app.services.risk_scoring import compute_risk_score
from app.services.payment_plan_service import recommend_payment_plan
from app.services.notification_service import send_reminder_to_guardian

router = APIRouter(
    prefix="/api/invoices",
    tags=["invoices"],
    dependencies=[Depends(require_roles("SCHOOL_ADMIN", "BURSAR"))],
)

MAX_PAGE_SIZE = 100


@router.get("", response_model=Page[InvoiceListItem])
def list_invoices(
    page: int = 1,
    page_size: int = 25,
    status: str | None = None,
    term_id: str | None = None,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

    base_filters = [Invoice.school_id == school_id]
    if status:
        base_filters.append(Invoice.status == status)
    if term_id:
        base_filters.append(Invoice.term_id == term_id)

    total = db.execute(select(func.count()).select_from(Invoice).where(*base_filters)).scalar_one()

    rows = db.execute(
        select(Invoice, Student, SchoolClass)
        .join(Student, Invoice.student_id == Student.id)
        .outerjoin(SchoolClass, Student.class_id == SchoolClass.id)
        .where(*base_filters)
        .order_by(Invoice.due_date)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        InvoiceListItem(
            **InvoiceResponse.model_validate(invoice).model_dump(),
            student_name=student.full_name,
            class_name=school_class.name if school_class else "—",
        )
        for invoice, student, school_class in rows
    ]

    return Page(
        items=items,
        meta=PageMeta(page=page, page_size=page_size, total=total, has_more=(page * page_size) < total),
    )


@router.post("", response_model=InvoiceResponse, status_code=201)
def create_invoice(
    data: GenerateInvoiceRequest,
    school_id: str = Depends(get_school_scope),  # noqa: ARG001 — enforced via student lookup in service
    db: Session = Depends(get_db),
):
    return generate_invoice_for_student(db, data.student_id, data.term_id, data.due_date)


@router.post("/bulk-generate", response_model=BulkGenerateResult, status_code=207)
def bulk_generate_invoices(
    data: BulkGenerateRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
):
    """Generates one invoice per active student in a class/school for a term."""
    query = select(Student).where(Student.school_id == school_id, Student.is_active == True)  # noqa: E712
    if data.class_id:
        query = query.where(Student.class_id == data.class_id)
    students = db.execute(query).scalars().all()

    created, skipped, errors = 0, 0, []
    for student in students:
        try:
            generate_invoice_for_student(db, student.id, data.term_id, data.due_date)
            created += 1
        except Exception as exc:  # noqa: BLE001 — intentionally broad: one bad student shouldn't stop the batch
            skipped += 1
            errors.append({"student_id": student.id, "error": str(exc)})

    return BulkGenerateResult(created=created, skipped=skipped, errors=errors)


@router.get("/{invoice_id}/risk", response_model=RiskAssessmentResponse)
def get_invoice_risk(
    invoice_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
):
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.school_id == school_id)
    ).scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    assessment = compute_risk_score(db, invoice.student_id, invoice_id)

    return RiskAssessmentResponse(
        score=assessment.score,
        level=assessment.level,
        factors=RiskFactorsResponse(
            history_score=assessment.factors.history_score,
            overdue_score=assessment.factors.overdue_score,
            balance_score=assessment.factors.balance_score,
            reversal_score=assessment.factors.reversal_score,
        ),
        explanation=assessment.explanation,
    )


@router.get("/{invoice_id}/payments", response_model=list[PaymentResponse])
def get_invoice_payments(
    invoice_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
):
    """Confirmed payments recorded against an invoice, most recent first —
    what the bursar-side receipt links are generated from."""
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.school_id == school_id)
    ).scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    payments = db.execute(
        select(Payment)
        .where(Payment.invoice_id == invoice_id, Payment.status == PaymentStatus.CONFIRMED, Payment.amount > 0)
        .order_by(Payment.paid_at.desc())
    ).scalars().all()

    return payments


@router.post("/{invoice_id}/send-reminder", response_model=SendReminderResponse)
def send_invoice_reminder(
    invoice_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
):
    """
    Sends a fee reminder (email + SMS, whichever are configured) to every
    APPROVED guardian linked to this invoice's student — deliberately
    excludes PENDING links, since those haven't been confirmed by a bursar
    yet and shouldn't be treated as a real point of contact.
    """
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.school_id == school_id)
    ).scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    balance = invoice.total_amount - invoice.amount_paid
    if balance <= 0:
        raise HTTPException(422, "This invoice is already fully paid — nothing to remind about")

    student = db.get(Student, invoice.student_id)
    school = db.get(School, school_id)
    if not student or not school:
        raise HTTPException(404, "Related record not found")

    links = db.execute(
        select(StudentGuardian).where(
            StudentGuardian.student_id == student.id,
            StudentGuardian.status == GuardianLinkStatus.APPROVED,
        )
    ).scalars().all()

    if not links:
        raise HTTPException(422, "No approved parent contacts linked to this student yet")

    results = []
    for link in links:
        guardian = db.get(User, link.user_id)
        if not guardian:
            continue
        outcome = send_reminder_to_guardian(
            guardian_email=guardian.email,
            guardian_phone=guardian.phone,
            student_name=student.full_name,
            school_name=school.name,
            balance=balance,
            currency=school.currency,
            due_date=invoice.due_date,
        )
        results.append(
            ReminderRecipientResult(
                guardian_email=outcome.guardian_email,
                guardian_phone=outcome.guardian_phone,
                email_sent=outcome.email_sent,
                sms_sent=outcome.sms_sent,
                errors=outcome.errors,
            )
        )

    return SendReminderResponse(recipients_notified=len(results), results=results)


@router.get("/{invoice_id}/payment-plan", response_model=PaymentPlanResponse)
def get_payment_plan(
    invoice_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
):
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.school_id == school_id)
    ).scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    plan = recommend_payment_plan(db, invoice.student_id, invoice_id)

    return PaymentPlanResponse(
        installments=[InstallmentResponse(amount=i.amount, due_date=i.due_date) for i in plan.installments],
        rationale=plan.rationale,
    )

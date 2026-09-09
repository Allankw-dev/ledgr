from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, require_roles, CurrentUser
from app.core.security import hash_password
from app.core.rate_limit import limiter
from app.schemas.student import CreateStudentRequest, StudentResponse, UpdateStudentClassRequest, UpdateStudentRequest
from app.schemas.pagination import Page, PageMeta
from app.schemas.guardian import LinkGuardianRequest, GuardianResponse
from app.schemas.guardian_request import (
    StudentLookupResult,
    RequestLinkPayload,
    PendingGuardianRequest,
    GuardianReviewResponse,
)
from app.models.student import Student, StudentGuardian, Term, SchoolClass
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.school import User, School
from app.models.enums import UserRole, GuardianLinkStatus, PaymentStatus
from app.services.statement_service import generate_fee_statement_pdf

router = APIRouter(prefix="/api/students", tags=["students"], dependencies=[Depends(get_current_user)])

MAX_PAGE_SIZE = 100


@router.get("", response_model=Page[StudentResponse])
def list_students(
    page: int = 1,
    page_size: int = 25,
    class_id: str | None = None,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

    filters = [Student.school_id == school_id, Student.is_active == True]  # noqa: E712
    if class_id:
        filters.append(Student.class_id == class_id)

    total = db.execute(select(func.count()).select_from(Student).where(*filters)).scalar_one()
    items = (
        db.execute(
            select(Student)
            .where(*filters)
            .order_by(Student.full_name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )

    return Page(
        items=items,
        meta=PageMeta(page=page, page_size=page_size, total=total, has_more=(page * page_size) < total),
    )


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(
    student_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
):
    # school_id filter enforces tenant isolation even if the id is guessed/leaked
    student = db.execute(
        select(Student).where(Student.id == student_id, Student.school_id == school_id)
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student not found")
    return student


@router.post("", response_model=StudentResponse, status_code=201)
def create_student(
    data: CreateStudentRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    student = Student(school_id=school_id, **data.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.patch("/{student_id}", response_model=StudentResponse)
def update_student(
    student_id: str,
    data: UpdateStudentRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    """Corrects details keyed in wrong at enrollment — name, admission
    number, date of birth. Separate from the /class endpoint so a routine
    grade promotion and a details correction stay two distinct actions."""
    student = db.execute(
        select(Student).where(Student.id == student_id, Student.school_id == school_id)
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(student, field, value)

    db.commit()
    db.refresh(student)
    return student


@router.patch("/{student_id}/class", response_model=StudentResponse)
def update_student_class(
    student_id: str,
    data: UpdateStudentClassRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    """Assign or reassign which grade/class a student belongs to — e.g. moving
    them up a grade at the start of a new year, or fixing a wrong grade set
    at enrollment. Setting class_id to null unassigns them (they'll only be
    reachable by whole-school announcements, not a grade-scoped one)."""
    student = db.execute(
        select(Student).where(Student.id == student_id, Student.school_id == school_id)
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student not found")

    if data.class_id:
        school_class = db.execute(
            select(SchoolClass).where(SchoolClass.id == data.class_id, SchoolClass.school_id == school_id)
        ).scalar_one_or_none()
        if not school_class:
            raise HTTPException(404, "Class not found")

    student.class_id = data.class_id
    db.commit()
    db.refresh(student)
    return student


@router.post("/{student_id}/deactivate", response_model=StudentResponse)
def deactivate_student(
    student_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    """
    Removes a student from active use — e.g. they've transferred to
    another school. This is a SOFT delete (is_active = False), never a
    hard delete: any invoices and payments tied to this student stay
    exactly as they are, since a school's financial records need to
    survive a student leaving. The student simply stops appearing in
    active lists (list_students already filters on is_active) and can no
    longer be billed going forward.
    """
    student = db.execute(
        select(Student).where(Student.id == student_id, Student.school_id == school_id)
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student not found")

    student.is_active = False
    db.commit()
    db.refresh(student)
    return student


@router.post("/{student_id}/guardians", response_model=GuardianResponse, status_code=201)
def link_guardian(
    student_id: str,
    data: LinkGuardianRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    """
    Links a parent account to a student, granting that parent portal access
    to this child's fee data. Reuses an existing user by email if one exists
    (e.g. adding a second child to the same parent) rather than creating a
    duplicate account or touching that user's existing password.
    """
    student = db.execute(
        select(Student).where(Student.id == student_id, Student.school_id == school_id)
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student not found")

    user = db.execute(select(User).where(User.email == data.email)).scalar_one_or_none()
    if user:
        if user.role != UserRole.PARENT or user.school_id != school_id:
            raise HTTPException(409, "This email is already registered with a different role or school")
    else:
        user = User(
            school_id=school_id,
            email=data.email,
            password_hash=hash_password(data.password),
            role=UserRole.PARENT,
            full_name=data.full_name,
            phone=data.phone,
        )
        db.add(user)
        db.flush()

    existing_link = db.execute(
        select(StudentGuardian).where(StudentGuardian.student_id == student_id, StudentGuardian.user_id == user.id)
    ).scalar_one_or_none()
    if existing_link:
        raise HTTPException(409, "This parent is already linked to this student")

    guardian = StudentGuardian(
        student_id=student_id,
        user_id=user.id,
        relationship_type=data.relationship_type,
        is_primary=data.is_primary,
    )
    db.add(guardian)
    db.commit()
    db.refresh(guardian)

    return GuardianResponse(
        id=guardian.id,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        relationship_type=guardian.relationship_type,
        is_primary=guardian.is_primary,
    )


@router.get("/lookup", response_model=StudentLookupResult)
@limiter.limit("10/minute")
def lookup_student(
    request: Request,
    admission_number: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Used right after a parent signs up: they type in their child's
    admission number and get back just enough to recognize them (name,
    class, school) — never balance or any financial detail, since an
    admission number alone is weak proof of identity. Rate-limited per
    caller specifically to blunt someone trying to enumerate valid numbers
    by trial and error now that they at least need a real account to try.
    """
    if user.role != "PARENT":
        raise HTTPException(403, "This endpoint is for parent accounts only")

    student = db.execute(
        select(Student).where(
            func.lower(Student.admission_number) == admission_number.strip().lower(),
            Student.school_id == school_id,
            Student.is_active == True,  # noqa: E712
        )
    ).scalar_one_or_none()

    if not student:
        # Deliberately generic — doesn't confirm or deny whether a number
        # format is "close" to a real one.
        raise HTTPException(404, "We couldn't find a student with that admission number.")

    from app.models.school import School as SchoolModel

    school = db.get(SchoolModel, school_id)

    return StudentLookupResult(
        student_id=student.id,
        full_name=student.full_name,
        class_name=student.school_class.name if student.school_class else None,
        school_name=school.name if school else "",
    )


@router.post("/{student_id}/request-link", response_model=GuardianResponse, status_code=201)
@limiter.limit("10/minute")
def request_link(
    request: Request,
    student_id: str,
    data: RequestLinkPayload,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    A parent's self-service request to be linked to a child, found via the
    lookup endpoint above. Always created as PENDING — this does NOT grant
    portal access on its own. A bursar must approve it (see
    /api/guardian-requests/{id}/approve) before get_my_children will
    return anything for this link.
    """
    if user.role != "PARENT":
        raise HTTPException(403, "This endpoint is for parent accounts only")

    student = db.execute(
        select(Student).where(Student.id == student_id, Student.school_id == school_id)
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student not found")

    existing_link = db.execute(
        select(StudentGuardian).where(
            StudentGuardian.student_id == student_id, StudentGuardian.user_id == user.user_id
        )
    ).scalar_one_or_none()
    if existing_link:
        raise HTTPException(409, "You've already requested (or been granted) a link to this student")

    guardian = StudentGuardian(
        student_id=student_id,
        user_id=user.user_id,
        relationship_type=data.relationship_type,
        is_primary=True,
        status=GuardianLinkStatus.PENDING,
    )
    db.add(guardian)
    db.commit()
    db.refresh(guardian)

    db_user = db.get(User, user.user_id)

    return GuardianResponse(
        id=guardian.id,
        user_id=user.user_id,
        full_name=db_user.full_name if db_user else "",
        email=db_user.email if db_user else "",
        phone=db_user.phone if db_user else None,
        relationship_type=guardian.relationship_type,
        is_primary=guardian.is_primary,
    )


guardian_requests_router = APIRouter(
    prefix="/api/guardian-requests", tags=["guardian-requests"], dependencies=[Depends(get_current_user)]
)


@guardian_requests_router.get("", response_model=list[PendingGuardianRequest])
def list_pending_requests(
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    """All parent self-service link requests awaiting bursar review."""
    links = db.execute(
        select(StudentGuardian)
        .join(Student, Student.id == StudentGuardian.student_id)
        .where(Student.school_id == school_id, StudentGuardian.status == GuardianLinkStatus.PENDING)
        .order_by(StudentGuardian.created_at)
    ).scalars().all()

    results = []
    for link in links:
        student = db.get(Student, link.student_id)
        parent = db.get(User, link.user_id)
        if not student or not parent:
            continue
        results.append(
            PendingGuardianRequest(
                id=link.id,
                student_id=student.id,
                student_name=student.full_name,
                parent_name=parent.full_name,
                parent_email=parent.email,
                relationship_type=link.relationship_type,
                requested_at=link.created_at,
            )
        )
    return results


@guardian_requests_router.post("/{link_id}/approve", response_model=GuardianReviewResponse)
def approve_request(
    link_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    link = db.execute(
        select(StudentGuardian)
        .join(Student, Student.id == StudentGuardian.student_id)
        .where(StudentGuardian.id == link_id, Student.school_id == school_id)
    ).scalar_one_or_none()
    if not link:
        raise HTTPException(404, "Request not found")

    link.status = GuardianLinkStatus.APPROVED
    db.commit()
    return GuardianReviewResponse(status="approved")


@guardian_requests_router.post("/{link_id}/reject", response_model=GuardianReviewResponse)
def reject_request(
    link_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    link = db.execute(
        select(StudentGuardian)
        .join(Student, Student.id == StudentGuardian.student_id)
        .where(StudentGuardian.id == link_id, Student.school_id == school_id)
    ).scalar_one_or_none()
    if not link:
        raise HTTPException(404, "Request not found")

    link.status = GuardianLinkStatus.REJECTED
    db.commit()
    return GuardianReviewResponse(status="rejected")


@router.get("/{student_id}/statement")
def download_fee_statement(
    student_id: str,
    term_id: str | None = None,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    A full fee statement PDF — every invoice and every payment for a
    student, optionally scoped to one term. Same authorization shape as
    receipts.download_receipt: a parent can only pull their own child's
    statement, staff can pull any student in their school.
    """
    student = db.execute(
        select(Student).where(Student.id == student_id, Student.school_id == school_id)
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student not found")

    if user.role == "PARENT":
        link = db.execute(
            select(StudentGuardian).where(
                StudentGuardian.student_id == student_id,
                StudentGuardian.user_id == user.user_id,
                StudentGuardian.status == GuardianLinkStatus.APPROVED,
            )
        ).scalar_one_or_none()
        if not link:
            raise HTTPException(403, "You don't have access to this student's statement")
    elif user.role not in ("SCHOOL_ADMIN", "BURSAR", "SUPER_ADMIN"):
        raise HTTPException(403, "Not authorized")

    school = db.get(School, school_id)
    school_class = db.get(SchoolClass, student.class_id) if student.class_id else None

    term = db.get(Term, term_id) if term_id else None
    if term_id and not term:
        raise HTTPException(404, "Term not found")

    invoice_query = select(Invoice).where(Invoice.student_id == student_id).order_by(Invoice.due_date.asc())
    if term_id:
        invoice_query = invoice_query.where(Invoice.term_id == term_id)
    invoice_rows = db.execute(invoice_query).scalars().all()

    all_term_ids = {inv.term_id for inv in invoice_rows} | ({term_id} if term_id else set())
    terms_by_id = {t.id: t for t in db.execute(select(Term).where(Term.id.in_(all_term_ids))).scalars().all()} if all_term_ids else {}

    invoice_ids = [inv.id for inv in invoice_rows]
    payment_query = select(Payment).where(
        Payment.student_id == student_id, Payment.status == PaymentStatus.CONFIRMED
    )
    if term:
        # Include payments tied to an invoice in this term, or unattached
        # payments that landed inside the term's date range.
        in_term_dates = Payment.invoice_id.is_(None) & Payment.paid_at.between(term.start_date, term.end_date)
        conditions = [in_term_dates]
        if invoice_ids:
            conditions.append(Payment.invoice_id.in_(invoice_ids))
        payment_query = payment_query.where(or_(*conditions))
    payment_rows = db.execute(payment_query).scalars().all()

    pdf_bytes = generate_fee_statement_pdf(
        school_name=school.name,
        student_name=student.full_name,
        admission_number=student.admission_number,
        class_name=school_class.name if school_class else None,
        currency=school.currency,
        period_label=term.name if term else "All terms",
        invoices=[
            {
                "term_name": terms_by_id.get(inv.term_id).name if terms_by_id.get(inv.term_id) else "—",
                "due_date": inv.due_date,
                "total_amount": inv.total_amount,
                "amount_paid": inv.amount_paid,
                "status": inv.status.value,
            }
            for inv in invoice_rows
        ],
        payments=[
            {
                "paid_at": p.paid_at,
                "amount": p.amount,
                "method": p.method.value,
                "reference_code": p.reference_code,
            }
            for p in payment_rows
        ],
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="statement-{student.admission_number}.pdf"'},
    )

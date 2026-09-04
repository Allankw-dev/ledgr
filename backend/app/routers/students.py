from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, require_roles, CurrentUser
from app.core.security import hash_password
from app.core.rate_limit import limiter
from app.schemas.student import CreateStudentRequest, StudentResponse
from app.schemas.guardian import LinkGuardianRequest, GuardianResponse
from app.schemas.guardian_request import (
    StudentLookupResult,
    RequestLinkPayload,
    PendingGuardianRequest,
    GuardianReviewResponse,
)
from app.models.student import Student, StudentGuardian
from app.models.school import User
from app.models.enums import UserRole, GuardianLinkStatus

router = APIRouter(prefix="/api/students", tags=["students"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[StudentResponse])
def list_students(
    class_id: str | None = None,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
):
    query = select(Student).where(Student.school_id == school_id, Student.is_active == True)  # noqa: E712
    if class_id:
        query = query.where(Student.class_id == class_id)
    return db.execute(query.order_by(Student.full_name)).scalars().all()


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

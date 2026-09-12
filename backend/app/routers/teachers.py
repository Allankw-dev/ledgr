import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_school_scope, require_roles, CurrentUser
from app.core.security import hash_password, create_password_reset_token
from app.core.config import settings
from app.core.rate_limit import limiter
from app.schemas.teacher import CreateTeacherRequest, UpdateTeacherClassesRequest, TeacherResponse
from app.models.school import User
from app.models.enums import UserRole
from app.models.student import SchoolClass
from app.models.teacher_class_assignment import TeacherClassAssignment
from app.services.notification_service import send_email, NotificationConfigError

router = APIRouter(prefix="/api/teachers", tags=["teachers"])


def _to_response(db: Session, teacher: User) -> TeacherResponse:
    assignments = db.execute(
        select(TeacherClassAssignment, SchoolClass)
        .join(SchoolClass, TeacherClassAssignment.class_id == SchoolClass.id)
        .where(TeacherClassAssignment.teacher_user_id == teacher.id)
    ).all()
    return TeacherResponse(
        id=teacher.id,
        full_name=teacher.full_name,
        email=teacher.email,
        is_active=teacher.is_active,
        created_at=teacher.created_at,
        class_ids=[sc.id for _, sc in assignments],
        class_names=[sc.name for _, sc in assignments],
    )


@router.get("", response_model=list[TeacherResponse])
def list_teachers(
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    teachers = db.execute(
        select(User).where(User.school_id == school_id, User.role == UserRole.TEACHER).order_by(User.full_name)
    ).scalars().all()
    return [_to_response(db, t) for t in teachers]


@router.post("", response_model=TeacherResponse, status_code=201)
@limiter.limit("10/minute")
def create_teacher(
    request: Request,
    data: CreateTeacherRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN")),
):
    """Only SCHOOL_ADMIN creates staff accounts — this is the one place a
    new login with real access to the school's data gets minted, so it's
    deliberately narrower than the BURSAR-inclusive roles most other admin
    endpoints accept.

    No password is set here or ever transmitted in plaintext: the account
    is created with an unusable random hash, then the teacher gets an
    emailed link (reusing the same password-reset flow a forgotten
    password uses) to set their own password before they can log in."""
    existing = db.execute(select(User).where(User.email == data.email)).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "An account with this email already exists")

    if data.class_ids:
        found = db.execute(
            select(SchoolClass.id).where(SchoolClass.id.in_(data.class_ids), SchoolClass.school_id == school_id)
        ).scalars().all()
        if set(found) != set(data.class_ids):
            raise HTTPException(404, "One or more selected grades were not found")

    teacher = User(
        school_id=school_id,
        email=data.email,
        password_hash=hash_password(uuid.uuid4().hex),
        role=UserRole.TEACHER,
        full_name=data.full_name,
    )
    db.add(teacher)
    db.flush()

    for class_id in data.class_ids:
        db.add(TeacherClassAssignment(teacher_user_id=teacher.id, class_id=class_id))

    db.commit()
    db.refresh(teacher)

    token = create_password_reset_token(teacher.id, teacher.password_hash)
    set_password_link = f"{settings.frontend_url}/reset-password?token={token}"
    try:
        send_email(
            teacher.email,
            "You've been added to Ledgr",
            f"Hi {teacher.full_name},\n\n"
            f"You've been set up with a teacher account on Ledgr. Set your password to get started "
            f"(this link expires in 30 minutes):\n\n{set_password_link}\n\n"
            f"If you weren't expecting this, you can ignore this email.",
        )
    except NotificationConfigError:
        pass

    return _to_response(db, teacher)


@router.patch("/{teacher_id}/classes", response_model=TeacherResponse)
def update_teacher_classes(
    teacher_id: str,
    data: UpdateTeacherClassesRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN")),
):
    teacher = db.execute(
        select(User).where(User.id == teacher_id, User.school_id == school_id, User.role == UserRole.TEACHER)
    ).scalar_one_or_none()
    if not teacher:
        raise HTTPException(404, "Teacher not found")

    if data.class_ids:
        found = db.execute(
            select(SchoolClass.id).where(SchoolClass.id.in_(data.class_ids), SchoolClass.school_id == school_id)
        ).scalars().all()
        if set(found) != set(data.class_ids):
            raise HTTPException(404, "One or more selected grades were not found")

    db.execute(
        TeacherClassAssignment.__table__.delete().where(TeacherClassAssignment.teacher_user_id == teacher_id)
    )
    for class_id in data.class_ids:
        db.add(TeacherClassAssignment(teacher_user_id=teacher_id, class_id=class_id))
    db.commit()

    return _to_response(db, teacher)

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_school_scope, require_roles, CurrentUser
from app.core.security import hash_password, create_password_reset_token
from app.core.config import settings
from app.core.phone import normalize_phone
from app.core.rate_limit import limiter
from app.schemas.teacher import CreateTeacherRequest, UpdateTeacherClassesRequest, TeacherResponse
from app.models.school import User
from app.models.enums import UserRole
from app.models.student import SchoolClass
from app.models.teacher_class_assignment import TeacherClassAssignment
from app.services.notification_service import send_email, send_sms, NotificationConfigError
from app.models.school import School

router = APIRouter(prefix="/api/teachers", tags=["teachers"])


PHONE_ONLY_EMAIL_DOMAIN = "phone.ledgr.invalid"  # reserved-invalid TLD: can never receive mail


def _display_email(user: User) -> str | None:
    return None if user.email.endswith("@" + PHONE_ONLY_EMAIL_DOMAIN) else user.email


def _send_invite(db: Session, teacher: User, school_id: str) -> list[str]:
    """Sends the set-password link by email and/or SMS, whichever the
    teacher has. Returns the channels that actually went out. The link is
    never returned to the admin — it only ever goes to the teacher."""
    token = create_password_reset_token(teacher.id, teacher.password_hash)
    link = f"{settings.frontend_url}/reset-password?token={token}"
    school = db.get(School, school_id)
    school_name = school.name if school else "your school"
    sent: list[str] = []

    if _display_email(teacher):
        try:
            send_email(
                teacher.email,
                "You've been added to Ledgr",
                f"Hi {teacher.full_name},\n\n"
                f"You've been set up with a teacher account on Ledgr for {school_name}. Set your password to get started "
                f"(this link expires in 30 minutes):\n\n{link}\n\n"
                f"If you weren't expecting this, you can ignore this email.",
            )
            sent.append("email")
        except NotificationConfigError:
            pass
        except Exception:  # noqa: BLE001 — a mail outage must not undo account creation
            pass

    if teacher.phone:
        try:
            send_sms(
                teacher.phone,
                f"Hi {teacher.full_name}, you've been added to {school_name} on Ledgr. "
                f"Set your password (link valid 30 min): {link}",
            )
            sent.append("sms")
        except NotificationConfigError:
            pass
        except Exception:  # noqa: BLE001
            pass
    return sent


def _to_response(db: Session, teacher: User, invite_channels: list[str] | None = None) -> TeacherResponse:
    assignments = db.execute(
        select(TeacherClassAssignment, SchoolClass)
        .join(SchoolClass, TeacherClassAssignment.class_id == SchoolClass.id)
        .where(TeacherClassAssignment.teacher_user_id == teacher.id)
    ).all()
    return TeacherResponse(
        id=teacher.id,
        full_name=teacher.full_name,
        email=_display_email(teacher),
        phone=teacher.phone,
        is_active=teacher.is_active,
        created_at=teacher.created_at,
        class_ids=[sc.id for _, sc in assignments],
        class_names=[sc.name for _, sc in assignments],
        invite_channels=invite_channels or [],
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
    if not teachers:
        return []

    # One query for every teacher's assignments, not one query per
    # teacher — the same N+1 pattern fixed in class_groups.py, here for a
    # school's teacher roster instead of a parent's unread count.
    teacher_ids = [t.id for t in teachers]
    assignment_rows = db.execute(
        select(TeacherClassAssignment.teacher_user_id, SchoolClass.id, SchoolClass.name)
        .join(SchoolClass, TeacherClassAssignment.class_id == SchoolClass.id)
        .where(TeacherClassAssignment.teacher_user_id.in_(teacher_ids))
    ).all()

    classes_by_teacher: dict[str, list[tuple[str, str]]] = {}
    for teacher_id, class_id, class_name in assignment_rows:
        classes_by_teacher.setdefault(teacher_id, []).append((class_id, class_name))

    return [
        TeacherResponse(
            id=t.id,
            full_name=t.full_name,
            email=_display_email(t),
            phone=t.phone,
            is_active=t.is_active,
            created_at=t.created_at,
            class_ids=[cid for cid, _ in classes_by_teacher.get(t.id, [])],
            class_names=[cname for _, cname in classes_by_teacher.get(t.id, [])],
        )
        for t in teachers
    ]


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
    phone = normalize_phone(data.phone) if data.phone and data.phone.strip() else None

    if data.email:
        if db.execute(select(User).where(User.email == data.email)).scalar_one_or_none():
            raise HTTPException(409, "An account with this email already exists")
    if phone:
        # Teachers sign in by phone, so a teacher's number must be unique platform-wide.
        if db.execute(select(User).where(User.phone == phone, User.role == UserRole.TEACHER)).scalar_one_or_none():
            raise HTTPException(409, "A teacher with this phone number already exists")

    if data.class_ids:
        found = db.execute(
            select(SchoolClass.id).where(SchoolClass.id.in_(data.class_ids), SchoolClass.school_id == school_id)
        ).scalars().all()
        if set(found) != set(data.class_ids):
            raise HTTPException(404, "One or more selected grades were not found")

    teacher = User(
        school_id=school_id,
        # Phone-only teachers get a placeholder address on a reserved-invalid
        # domain (the users table requires a unique email); it's hidden in the UI.
        email=data.email or f"t-{uuid.uuid4().hex[:12]}@{PHONE_ONLY_EMAIL_DOMAIN}",
        phone=phone,
        password_hash=hash_password(uuid.uuid4().hex),
        role=UserRole.TEACHER,
        full_name=data.full_name,
        is_active=True,
    )
    db.add(teacher)
    db.flush()

    for class_id in data.class_ids:
        db.add(TeacherClassAssignment(teacher_user_id=teacher.id, class_id=class_id))

    try:
        db.commit()
    except IntegrityError:
        # The pre-checks above only see THIS school's rows (row-level security),
        # but emails and teacher phone numbers are unique across the whole
        # platform — so a clash with another school surfaces here.
        db.rollback()
        raise HTTPException(409, "That email address or phone number is already registered to another account")
    db.refresh(teacher)

    channels = _send_invite(db, teacher, school_id)
    return _to_response(db, teacher, channels)


@router.post("/{teacher_id}/resend-invite", response_model=TeacherResponse)
@limiter.limit("10/hour")
def resend_teacher_invite(
    request: Request,
    teacher_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN")),
):
    """Re-sends the set-password link (e.g. it expired, or SMS/email wasn't
    configured the first time)."""
    teacher = db.execute(
        select(User).where(User.id == teacher_id, User.school_id == school_id, User.role == UserRole.TEACHER)
    ).scalar_one_or_none()
    if not teacher:
        raise HTTPException(404, "Teacher not found")
    channels = _send_invite(db, teacher, school_id)
    return _to_response(db, teacher, channels)


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

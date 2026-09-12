from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, CurrentUser
from app.schemas.class_group import ClassGroupSummary, ClassGroupMessageResponse, SendClassGroupMessageRequest
from app.models.school import User
from app.models.enums import UserRole
from app.models.student import SchoolClass, Student, StudentGuardian
from app.models.teacher_class_assignment import TeacherClassAssignment
from app.models.class_group_message import ClassGroupMessage

router = APIRouter(prefix="/api/class-groups", tags=["class-groups"], dependencies=[Depends(get_current_user)])

STAFF_ROLES = ("SCHOOL_ADMIN", "BURSAR")

# How many messages a thread loads at once. This is a broadcast group, not
# a paginated table — like any chat app, what matters is a recent window
# to scroll from, not the full history up front.
MESSAGE_WINDOW = 200


def _accessible_class_ids(db: Session, user: CurrentUser, school_id: str) -> set[str]:
    """The set of grades this user is allowed to see/post in. Staff get
    every grade in the school — bursar's office is a member of every
    class group by design, same as it would be in a real WhatsApp group
    for each class. Teachers get only their assigned grades. Parents get
    only the grade(s) their own children are actually in."""
    if user.role in STAFF_ROLES:
        rows = db.execute(select(SchoolClass.id).where(SchoolClass.school_id == school_id)).scalars().all()
        return set(rows)

    if user.role == "TEACHER":
        rows = db.execute(
            select(TeacherClassAssignment.class_id).where(TeacherClassAssignment.teacher_user_id == user.user_id)
        ).scalars().all()
        return set(rows)

    if user.role == "PARENT":
        rows = db.execute(
            select(Student.class_id)
            .join(StudentGuardian, StudentGuardian.student_id == Student.id)
            .where(StudentGuardian.user_id == user.user_id, Student.class_id.is_not(None))
        ).scalars().all()
        return set(rows)

    return set()


def _require_class_access(db: Session, user: CurrentUser, school_id: str, class_id: str) -> None:
    if class_id not in _accessible_class_ids(db, user, school_id):
        raise HTTPException(403, "You don't have access to this class group")


@router.get("", response_model=list[ClassGroupSummary])
def list_class_groups(
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    class_ids = _accessible_class_ids(db, user, school_id)
    if not class_ids:
        return []

    classes = db.execute(
        select(SchoolClass).where(SchoolClass.id.in_(class_ids)).order_by(SchoolClass.name)
    ).scalars().all()

    # One query for the latest message per accessible class, rather than
    # N+1 — a subquery per class group would get slow once a school has a
    # couple dozen grades.
    latest_per_class: dict[str, ClassGroupMessage] = {}
    if class_ids:
        rows = db.execute(
            select(ClassGroupMessage)
            .where(ClassGroupMessage.class_id.in_(class_ids))
            .order_by(ClassGroupMessage.created_at.desc())
        ).scalars().all()
        for msg in rows:
            if msg.class_id not in latest_per_class:
                latest_per_class[msg.class_id] = msg

    return [
        ClassGroupSummary(
            class_id=sc.id,
            class_name=sc.name,
            last_message_preview=(
                latest_per_class[sc.id].body[:120] if sc.id in latest_per_class else None
            ),
            last_message_at=latest_per_class[sc.id].created_at if sc.id in latest_per_class else None,
        )
        for sc in classes
    ]


@router.get("/{class_id}/messages", response_model=list[ClassGroupMessageResponse])
def list_class_group_messages(
    class_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _require_class_access(db, user, school_id, class_id)

    rows = db.execute(
        select(ClassGroupMessage, User)
        .join(User, ClassGroupMessage.sender_user_id == User.id)
        .where(ClassGroupMessage.class_id == class_id)
        .order_by(ClassGroupMessage.created_at.desc())
        .limit(MESSAGE_WINDOW)
    ).all()

    return [
        ClassGroupMessageResponse(
            id=msg.id,
            class_id=msg.class_id,
            sender_user_id=msg.sender_user_id,
            sender_name=sender.full_name,
            sender_role=sender.role.value,
            body=msg.body,
            created_at=msg.created_at,
        )
        for msg, sender in reversed(rows)
    ]


@router.post("/{class_id}/messages", response_model=ClassGroupMessageResponse, status_code=201)
def send_class_group_message(
    class_id: str,
    data: SendClassGroupMessageRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _require_class_access(db, user, school_id, class_id)

    sender = db.get(User, user.user_id)
    if not sender:
        raise HTTPException(404, "User not found")

    message = ClassGroupMessage(
        school_id=school_id,
        class_id=class_id,
        sender_user_id=user.user_id,
        body=data.body,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    return ClassGroupMessageResponse(
        id=message.id,
        class_id=message.class_id,
        sender_user_id=message.sender_user_id,
        sender_name=sender.full_name,
        sender_role=sender.role.value,
        body=message.body,
        created_at=message.created_at,
    )

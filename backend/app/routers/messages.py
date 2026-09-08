from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, require_roles, CurrentUser
from app.models.school import User
from app.models.student import StudentGuardian
from app.models.enums import UserRole, MessageSenderRole, GuardianLinkStatus
from app.schemas.message import SendMessageRequest, MessageOut, ConversationSummary
from app.services.message_service import (
    send_message,
    list_conversation,
    mark_read_by_parent,
    mark_read_by_staff,
    list_conversations_for_school,
)

router = APIRouter(prefix="/api", tags=["messages"], dependencies=[Depends(get_current_user)])


def _validate_student_context(db: Session, school_id: str, parent_user_id: str, student_id: str | None) -> None:
    """If a message names a student, make sure that parent is actually
    APPROVED-linked to that student — otherwise a parent could reference
    (and a bursar could see referenced in the inbox) a child that isn't
    theirs."""
    if not student_id:
        return
    link = db.execute(
        select(StudentGuardian).where(
            StudentGuardian.student_id == student_id,
            StudentGuardian.user_id == parent_user_id,
            StudentGuardian.status == GuardianLinkStatus.APPROVED,
        )
    ).scalar_one_or_none()
    if not link:
        raise HTTPException(422, "That student isn't linked to this parent account")


@router.get("/parent/messages", response_model=list[MessageOut])
def get_my_messages(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    school_id: str = Depends(get_school_scope),
):
    if user.role != "PARENT":
        raise HTTPException(403, "This endpoint is for parent accounts only")
    messages = list_conversation(db, school_id, user.user_id)
    mark_read_by_parent(db, school_id, user.user_id)
    return messages


@router.post("/parent/messages", response_model=MessageOut)
def post_my_message(
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    school_id: str = Depends(get_school_scope),
):
    if user.role != "PARENT":
        raise HTTPException(403, "This endpoint is for parent accounts only")
    _validate_student_context(db, school_id, user.user_id, payload.student_id)
    msg = send_message(
        db,
        school_id=school_id,
        parent_user_id=user.user_id,
        sender_user_id=user.user_id,
        sender_role=MessageSenderRole.PARENT,
        body=payload.body,
        student_id=payload.student_id,
    )
    return _to_message_out(db, msg)


@router.get("/messages/conversations", response_model=list[ConversationSummary])
def get_conversations(
    db: Session = Depends(get_db),
    school_id: str = Depends(get_school_scope),
    user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    return list_conversations_for_school(db, school_id)


@router.get("/messages/conversations/{parent_user_id}", response_model=list[MessageOut])
def get_conversation(
    parent_user_id: str,
    db: Session = Depends(get_db),
    school_id: str = Depends(get_school_scope),
    user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    parent = db.execute(
        select(User).where(User.id == parent_user_id, User.school_id == school_id, User.role == UserRole.PARENT)
    ).scalar_one_or_none()
    if not parent:
        raise HTTPException(404, "Parent not found")
    messages = list_conversation(db, school_id, parent_user_id)
    mark_read_by_staff(db, school_id, parent_user_id)
    return messages


@router.post("/messages/conversations/{parent_user_id}", response_model=MessageOut)
def post_conversation_reply(
    parent_user_id: str,
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
    school_id: str = Depends(get_school_scope),
    user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    parent = db.execute(
        select(User).where(User.id == parent_user_id, User.school_id == school_id, User.role == UserRole.PARENT)
    ).scalar_one_or_none()
    if not parent:
        raise HTTPException(404, "Parent not found")
    _validate_student_context(db, school_id, parent_user_id, payload.student_id)
    msg = send_message(
        db,
        school_id=school_id,
        parent_user_id=parent_user_id,
        sender_user_id=user.user_id,
        sender_role=MessageSenderRole.STAFF,
        body=payload.body,
        student_id=payload.student_id,
    )
    return _to_message_out(db, msg)


def _to_message_out(db: Session, msg) -> dict:
    sender = db.get(User, msg.sender_user_id)
    student_name = None
    if msg.student_id:
        from app.models.student import Student

        student = db.get(Student, msg.student_id)
        student_name = student.full_name if student else None
    return {
        "id": msg.id,
        "sender_role": msg.sender_role.value,
        "sender_name": sender.full_name if sender else "Unknown",
        "body": msg.body,
        "student_id": msg.student_id,
        "student_name": student_name,
        "created_at": msg.created_at.isoformat(),
    }

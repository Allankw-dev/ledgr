"""Private one-to-one chats between a teacher and a parent.

Rules:
  * A teacher can chat with parents whose (approved) child is in a grade the
    teacher is assigned to; a parent can chat with their child's teachers.
  * Only the two participants can read a conversation. Other staff and the
    school admin cannot; someone else's conversation id looks like it doesn't exist.
  * Message text is stored encrypted (AES-256-GCM, see core/message_crypto.py).
  * Sending re-checks the relationship every time, so a teacher who is
    unassigned from a grade can't keep messaging that grade's parents.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, CurrentUser
from app.core.message_crypto import encrypt_text, decrypt_text, DecryptionError
from app.core.rate_limit import limiter
from app.models.direct_message import DirectConversation, DirectMessage
from app.models.enums import GuardianLinkStatus, UserRole
from app.models.school import User, gen_uuid
from app.models.student import SchoolClass, Student, StudentGuardian
from app.models.teacher_class_assignment import TeacherClassAssignment
from app.schemas.direct import (
    DirectContact,
    DirectConversationOut,
    DirectMessageOut,
    SendDirectMessageRequest,
    StartConversationRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/direct", tags=["direct-messages"], dependencies=[Depends(get_current_user)])

MESSAGE_WINDOW = 300


def _require_chat_role(user: CurrentUser) -> None:
    if user.role not in ("TEACHER", "PARENT"):
        raise HTTPException(403, "Private chats are between teachers and parents")


def _eligible_contacts(db: Session, user: CurrentUser, school_id: str) -> dict[str, dict]:
    """user_id -> {name, role, subtitle} for everyone this person may chat with."""
    contacts: dict[str, dict] = {}

    if user.role == "TEACHER":
        rows = db.execute(
            select(User.id, User.full_name, Student.full_name, SchoolClass.name)
            .select_from(StudentGuardian)
            .join(Student, Student.id == StudentGuardian.student_id)
            .join(User, User.id == StudentGuardian.user_id)
            .join(SchoolClass, SchoolClass.id == Student.class_id)
            .join(
                TeacherClassAssignment,
                (TeacherClassAssignment.class_id == Student.class_id) & (TeacherClassAssignment.teacher_user_id == user.user_id),
            )
            .where(
                StudentGuardian.status == GuardianLinkStatus.APPROVED,
                User.is_active.is_(True),
                User.role == UserRole.PARENT,
                Student.school_id == school_id,
            )
            .order_by(Student.full_name)
        ).all()
        kids: dict[str, list[str]] = {}
        for uid, name, child, cls in rows:
            contacts.setdefault(uid, {"name": name, "role": "PARENT"})
            kids.setdefault(uid, []).append(f"{child.split(' ')[0]} ({cls})")
        for uid, k in kids.items():
            contacts[uid]["subtitle"] = "Parent of " + ", ".join(dict.fromkeys(k))
    else:
        rows = db.execute(
            select(User.id, User.full_name, SchoolClass.name)
            .select_from(StudentGuardian)
            .join(Student, Student.id == StudentGuardian.student_id)
            .join(SchoolClass, SchoolClass.id == Student.class_id)
            .join(TeacherClassAssignment, TeacherClassAssignment.class_id == Student.class_id)
            .join(User, User.id == TeacherClassAssignment.teacher_user_id)
            .where(
                StudentGuardian.user_id == user.user_id,
                StudentGuardian.status == GuardianLinkStatus.APPROVED,
                User.is_active.is_(True),
                Student.school_id == school_id,
            )
        ).all()
        classes: dict[str, list[str]] = {}
        for uid, name, cls in rows:
            contacts.setdefault(uid, {"name": name, "role": "TEACHER"})
            classes.setdefault(uid, []).append(cls)
        for uid, c in classes.items():
            contacts[uid]["subtitle"] = "Teacher · " + ", ".join(dict.fromkeys(c))
    return contacts


def _get_conversation(db: Session, user: CurrentUser, conversation_id: str) -> DirectConversation:
    """404 (not 403) for someone else's conversation: don't confirm it exists."""
    conv = db.execute(
        select(DirectConversation).where(
            DirectConversation.id == conversation_id,
            (DirectConversation.teacher_user_id == user.user_id) | (DirectConversation.parent_user_id == user.user_id),
        )
    ).scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


def _other_id(conv: DirectConversation, me: str) -> str:
    return conv.parent_user_id if conv.teacher_user_id == me else conv.teacher_user_id


def _read_text(msg: DirectMessage) -> str:
    try:
        return decrypt_text(msg.body_enc, msg.conversation_id, msg.id, msg.sender_user_id)
    except DecryptionError:
        logger.error("Could not decrypt direct message %s (key missing/rotated out, or the row was tampered with)", msg.id)
        return "⚠️ This message can't be displayed."


def _build_conversations(db: Session, user: CurrentUser, school_id: str, convs: list[DirectConversation]) -> list[DirectConversationOut]:
    if not convs:
        return []
    contacts = _eligible_contacts(db, user, school_id)
    ids = [c.id for c in convs]
    other_ids = [_other_id(c, user.user_id) for c in convs]
    people = {uid: (name, role) for uid, name, role in db.execute(select(User.id, User.full_name, User.role).where(User.id.in_(other_ids))).all()}

    last = {
        m.conversation_id: m
        for m in db.execute(
            select(DirectMessage)
            .where(DirectMessage.conversation_id.in_(ids))
            .order_by(DirectMessage.conversation_id, DirectMessage.created_at.desc())
            .distinct(DirectMessage.conversation_id)
        ).scalars().all()
    }
    unread = dict(
        db.execute(
            select(DirectMessage.conversation_id, func.count())
            .where(
                DirectMessage.conversation_id.in_(ids),
                DirectMessage.sender_user_id != user.user_id,
                DirectMessage.read_at.is_(None),
            )
            .group_by(DirectMessage.conversation_id)
        ).all()
    )

    out = []
    for c in convs:
        oid = _other_id(c, user.user_id)
        name, role = people.get(oid, ("Unknown", "PARENT"))
        m = last.get(c.id)
        out.append(
            DirectConversationOut(
                id=c.id,
                other_user_id=oid,
                other_name=name,
                other_role=role.value if hasattr(role, "value") else str(role),
                other_subtitle=contacts.get(oid, {}).get("subtitle", "Teacher" if user.role == "PARENT" else "Parent"),
                last_message_preview=(_read_text(m)[:80] if m else None),
                last_message_at=m.created_at if m else None,
                unread_count=unread.get(c.id, 0),
                can_send=oid in contacts,
            )
        )
    out.sort(key=lambda x: x.last_message_at.timestamp() if x.last_message_at else 0, reverse=True)
    return out


@router.get("/contacts", response_model=list[DirectContact])
def list_contacts(
    q: str = "",
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """The people you can start a private chat with (a teacher's list is the
    parents of their grades; a parent's list is their children's teachers)."""
    _require_chat_role(user)
    contacts = _eligible_contacts(db, user, school_id)
    needle = q.strip().lower()

    convs = db.execute(
        select(DirectConversation).where(
            (DirectConversation.teacher_user_id == user.user_id) | (DirectConversation.parent_user_id == user.user_id)
        )
    ).scalars().all()
    by_other = {_other_id(c, user.user_id): c.id for c in convs}
    unread = dict(
        db.execute(
            select(DirectMessage.conversation_id, func.count())
            .where(
                DirectMessage.conversation_id.in_([c.id for c in convs] or [""]),
                DirectMessage.sender_user_id != user.user_id,
                DirectMessage.read_at.is_(None),
            )
            .group_by(DirectMessage.conversation_id)
        ).all()
    )

    result = [
        DirectContact(
            user_id=uid,
            name=c["name"],
            subtitle=c["subtitle"],
            conversation_id=by_other.get(uid),
            unread_count=unread.get(by_other.get(uid, ""), 0),
        )
        for uid, c in contacts.items()
        if not needle or needle in c["name"].lower() or needle in c["subtitle"].lower()
    ]
    result.sort(key=lambda r: r.name.lower())
    return result[:200]


@router.get("/conversations", response_model=list[DirectConversationOut])
def list_conversations(
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _require_chat_role(user)
    convs = db.execute(
        select(DirectConversation).where(
            (DirectConversation.teacher_user_id == user.user_id) | (DirectConversation.parent_user_id == user.user_id)
        )
    ).scalars().all()
    return _build_conversations(db, user, school_id, list(convs))


@router.post("/conversations", response_model=DirectConversationOut)
def start_conversation(
    data: StartConversationRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Start (or reopen) a private chat with someone from your list."""
    _require_chat_role(user)
    if data.user_id not in _eligible_contacts(db, user, school_id):
        raise HTTPException(403, "You can only start a private chat with the parents of your grades (or your child's teachers)")

    teacher_id, parent_id = (user.user_id, data.user_id) if user.role == "TEACHER" else (data.user_id, user.user_id)
    conv = db.execute(
        select(DirectConversation).where(
            DirectConversation.teacher_user_id == teacher_id, DirectConversation.parent_user_id == parent_id
        )
    ).scalar_one_or_none()
    if not conv:
        try:
            with db.begin_nested():
                conv = DirectConversation(school_id=school_id, teacher_user_id=teacher_id, parent_user_id=parent_id)
                db.add(conv)
                db.flush()
        except IntegrityError:  # created a moment ago by the other person
            conv = db.execute(
                select(DirectConversation).where(
                    DirectConversation.teacher_user_id == teacher_id, DirectConversation.parent_user_id == parent_id
                )
            ).scalar_one()
        db.commit()
    return _build_conversations(db, user, school_id, [conv])[0]


@router.get("/conversations/{conversation_id}/messages", response_model=list[DirectMessageOut])
def get_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    _school_id: str = Depends(get_school_scope),
):
    _require_chat_role(user)
    conv = _get_conversation(db, user, conversation_id)

    rows = db.execute(
        select(DirectMessage)
        .where(DirectMessage.conversation_id == conv.id)
        .order_by(DirectMessage.created_at.desc())
        .limit(MESSAGE_WINDOW)
    ).scalars().all()
    rows.reverse()

    result = []
    for m in rows:
        status = None
        if m.sender_user_id == user.user_id:
            status = "read" if m.read_at else "delivered" if m.delivered_at else "sent"
        result.append(
            DirectMessageOut(
                id=m.id, conversation_id=m.conversation_id, sender_user_id=m.sender_user_id,
                body=_read_text(m), created_at=m.created_at, status=status,
            )
        )

    # Opening the conversation = reading it (and it obviously reached this device).
    db.execute(
        update(DirectMessage)
        .where(
            DirectMessage.conversation_id == conv.id,
            DirectMessage.sender_user_id != user.user_id,
            DirectMessage.read_at.is_(None),
        )
        .values(read_at=func.clock_timestamp(), delivered_at=func.coalesce(DirectMessage.delivered_at, func.clock_timestamp()))
    )
    db.commit()
    return result


@router.post("/conversations/{conversation_id}/messages", response_model=DirectMessageOut, status_code=201)
@limiter.limit("60/minute")
def send_message(
    request: Request,
    conversation_id: str,
    data: SendDirectMessageRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _require_chat_role(user)
    conv = _get_conversation(db, user, conversation_id)
    if _other_id(conv, user.user_id) not in _eligible_contacts(db, user, school_id):
        raise HTTPException(403, "You can no longer message this person (they're no longer linked to your grade or child)")

    body = data.body.strip()
    if not body:
        raise HTTPException(422, "Write a message first")

    message_id = gen_uuid()
    token, version = encrypt_text(body, conv.id, message_id, user.user_id)
    msg = DirectMessage(
        id=message_id, school_id=school_id, conversation_id=conv.id, sender_user_id=user.user_id,
        body_enc=token, key_version=version,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return DirectMessageOut(
        id=msg.id, conversation_id=msg.conversation_id, sender_user_id=msg.sender_user_id,
        body=body, created_at=msg.created_at, status="sent",
    )

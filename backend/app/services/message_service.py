from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.message import Message
from app.models.school import User
from app.models.student import Student
from app.models.enums import MessageSenderRole
from app.models.typing_status import TypingStatus

# How long a typing ping stays "fresh" before the indicator clears itself.
# Comfortably longer than the client's ~2s ping interval so a normal pause
# between keystrokes doesn't flicker the indicator off and on.
TYPING_TTL = timedelta(seconds=4)


# Most recent messages returned per conversation thread.
MAX_THREAD_MESSAGES = 300


def send_message(
    db: Session,
    school_id: str,
    parent_user_id: str,
    sender_user_id: str,
    sender_role: MessageSenderRole,
    body: str,
    student_id: str | None = None,
) -> Message:
    msg = Message(
        school_id=school_id,
        parent_user_id=parent_user_id,
        sender_user_id=sender_user_id,
        sender_role=sender_role,
        body=body,
        student_id=student_id,
        # The sender has, definitionally, already "read" their own message —
        # mark it read on their own side immediately so it never inflates
        # their own unread count.
        read_by_parent_at=datetime.now(timezone.utc) if sender_role == MessageSenderRole.PARENT else None,
        read_by_staff_at=datetime.now(timezone.utc) if sender_role == MessageSenderRole.STAFF else None,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def _serialize_messages(db: Session, messages: list[Message]) -> list[dict]:
    user_ids = {m.sender_user_id for m in messages}
    student_ids = {m.student_id for m in messages if m.student_id}

    users_by_id = {u.id: u for u in db.execute(select(User).where(User.id.in_(user_ids))).scalars().all()} if user_ids else {}
    students_by_id = (
        {s.id: s for s in db.execute(select(Student).where(Student.id.in_(student_ids))).scalars().all()}
        if student_ids
        else {}
    )

    def _read_at(m: Message) -> str | None:
        # The relevant "has this been read" timestamp is always the OTHER
        # side's read column — a parent's sent message cares whether staff
        # read it, not whether the parent (its own sender) has.
        other_side_read = m.read_by_staff_at if m.sender_role == MessageSenderRole.PARENT else m.read_by_parent_at
        return other_side_read.isoformat() if other_side_read else None

    return [
        {
            "id": m.id,
            "sender_role": m.sender_role.value,
            "sender_name": users_by_id[m.sender_user_id].full_name if m.sender_user_id in users_by_id else "Unknown",
            "body": m.body,
            "student_id": m.student_id,
            "student_name": students_by_id[m.student_id].full_name if m.student_id in students_by_id else None,
            "created_at": m.created_at.isoformat(),
            "read_at": _read_at(m),
        }
        for m in messages
    ]


def list_conversation(db: Session, school_id: str, parent_user_id: str) -> list[dict]:
    # The thread is re-fetched on every poll, so cap it to the most recent
    # messages (newest N, returned oldest-first) — an old, very long thread
    # must not make every poll transfer and serialize its entire history.
    messages = db.execute(
        select(Message)
        .where(Message.school_id == school_id, Message.parent_user_id == parent_user_id)
        .order_by(Message.created_at.desc())
        .limit(MAX_THREAD_MESSAGES)
    ).scalars().all()
    messages.reverse()
    return _serialize_messages(db, messages)


def mark_read_by_parent(db: Session, school_id: str, parent_user_id: str) -> None:
    db.execute(
        Message.__table__.update()
        .where(
            Message.school_id == school_id,
            Message.parent_user_id == parent_user_id,
            Message.sender_role == MessageSenderRole.STAFF,
            Message.read_by_parent_at.is_(None),
        )
        .values(read_by_parent_at=datetime.now(timezone.utc))
    )
    db.commit()


def mark_read_by_staff(db: Session, school_id: str, parent_user_id: str) -> None:
    db.execute(
        Message.__table__.update()
        .where(
            Message.school_id == school_id,
            Message.parent_user_id == parent_user_id,
            Message.sender_role == MessageSenderRole.PARENT,
            Message.read_by_staff_at.is_(None),
        )
        .values(read_by_staff_at=datetime.now(timezone.utc))
    )
    db.commit()


def ping_typing(db: Session, school_id: str, parent_user_id: str, *, is_parent: bool) -> None:
    """Upsert this side's last-typed-at timestamp for the conversation.
    One row per (school, parent) regardless of which side is pinging, so
    this is a single upsert rather than a lookup-then-update — cheap
    enough to call on every debounced keystroke."""
    column = "parent_typing_at" if is_parent else "staff_typing_at"
    now = datetime.now(timezone.utc)
    stmt = (
        pg_insert(TypingStatus.__table__)
        .values(school_id=school_id, parent_user_id=parent_user_id, **{column: now})
        .on_conflict_do_update(
            index_elements=["school_id", "parent_user_id"],
            set_={column: now},
        )
    )
    db.execute(stmt)
    db.commit()


def get_typing_status(db: Session, school_id: str, parent_user_id: str, *, is_parent: bool) -> bool:
    """Is the OTHER side's most recent ping still fresh? is_parent=True
    means "I am the parent asking about staff", so we check staff_typing_at,
    and vice versa."""
    row = db.get(TypingStatus, {"school_id": school_id, "parent_user_id": parent_user_id})
    if not row:
        return False
    other_typing_at = row.staff_typing_at if is_parent else row.parent_typing_at
    if not other_typing_at:
        return False
    return datetime.now(timezone.utc) - other_typing_at < TYPING_TTL


def list_conversations_for_school(db: Session, school_id: str) -> list[dict]:
    """One row per parent who has ever messaged this school, newest first,
    with an unread count of their messages staff hasn't opened yet."""
    last_msg_subq = (
        select(
            Message.parent_user_id,
            func.max(Message.created_at).label("last_at"),
        )
        .where(Message.school_id == school_id)
        .group_by(Message.parent_user_id)
        .subquery()
    )

    last_messages = db.execute(
        select(Message)
        .join(
            last_msg_subq,
            and_(
                Message.parent_user_id == last_msg_subq.c.parent_user_id,
                Message.created_at == last_msg_subq.c.last_at,
            ),
        )
        .where(Message.school_id == school_id)
        .order_by(Message.created_at.desc())
    ).scalars().all()

    unread_counts = dict(
        db.execute(
            select(Message.parent_user_id, func.count(Message.id))
            .where(
                Message.school_id == school_id,
                Message.sender_role == MessageSenderRole.PARENT,
                Message.read_by_staff_at.is_(None),
            )
            .group_by(Message.parent_user_id)
        ).all()
    )

    parent_ids = {m.parent_user_id for m in last_messages}
    parents_by_id = {u.id: u for u in db.execute(select(User).where(User.id.in_(parent_ids))).scalars().all()} if parent_ids else {}

    return [
        {
            "parent_user_id": m.parent_user_id,
            "parent_name": parents_by_id[m.parent_user_id].full_name if m.parent_user_id in parents_by_id else "Unknown",
            "last_message_body": m.body,
            "last_message_at": m.created_at.isoformat(),
            "last_message_sender_role": m.sender_role.value,
            "unread_count": unread_counts.get(m.parent_user_id, 0),
        }
        for m in last_messages
    ]

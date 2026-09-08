from datetime import datetime, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.models.message import Message
from app.models.school import User
from app.models.student import Student
from app.models.enums import MessageSenderRole


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

    return [
        {
            "id": m.id,
            "sender_role": m.sender_role.value,
            "sender_name": users_by_id[m.sender_user_id].full_name if m.sender_user_id in users_by_id else "Unknown",
            "body": m.body,
            "student_id": m.student_id,
            "student_name": students_by_id[m.student_id].full_name if m.student_id in students_by_id else None,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


def list_conversation(db: Session, school_id: str, parent_user_id: str) -> list[dict]:
    messages = db.execute(
        select(Message)
        .where(Message.school_id == school_id, Message.parent_user_id == parent_user_id)
        .order_by(Message.created_at.asc())
    ).scalars().all()
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

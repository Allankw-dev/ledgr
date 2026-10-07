from fastapi import APIRouter, Depends, Request
from sqlalchemy import literal, select, func, update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, CurrentUser
from app.core.rate_limit import limiter
from app.models.class_group_message import ClassGroupMention, ClassGroupMessage
from app.models.enums import MessageSenderRole
from app.models.message import Message
from app.models.direct_message import DirectConversation, DirectMessage, DirectReport
from app.models.school import User
from app.models.student import SchoolClass
from app.routers.class_groups import _accessible_class_ids, mark_class_groups_delivered, unread_class_groups_subquery
from app.schemas.notification import AllNotificationsSummary, MentionNotification, MarkMentionsSeenRequest

router = APIRouter(prefix="/api/notifications", tags=["notifications"], dependencies=[Depends(get_current_user)])


@router.get("/summary", response_model=AllNotificationsSummary)
@limiter.limit("60/minute")
def get_summary(
    request: Request,
    db: Session = Depends(get_db),
    school_id: str = Depends(get_school_scope),
    user: CurrentUser = Depends(get_current_user),
):
    """One poll for every "something new" indicator, for every role.
    Polling this also records that the person's app is online, which is what
    turns a sender's single grey tick into two (delivered).

    This runs every ~25 s for every logged-in person, and each database round trip costs a
    real network hop to a hosted database (hundreds of ms when the app and database are in
    different regions). It used to take 15 round trips; it now takes about 5: the person's
    classes are looked up once, a poll that has nothing new to record writes and commits
    nothing, and every count comes back from a single SELECT."""
    class_ids = _accessible_class_ids(db, user, school_id)
    mark_class_groups_delivered(db, user, school_id, class_ids)

    if user.role in ("TEACHER", "PARENT"):
        mine = select(DirectConversation.id).where(
            (DirectConversation.teacher_user_id == user.user_id) | (DirectConversation.parent_user_id == user.user_id)
        )
        # The person's app just reached the server: their incoming private messages are now "delivered".
        delivered = db.execute(
            update(DirectMessage)
            .where(
                DirectMessage.delivered_at.is_(None),
                DirectMessage.sender_user_id != user.user_id,
                DirectMessage.conversation_id.in_(mine),
            )
            .values(delivered_at=func.clock_timestamp())
        )
        if delivered.rowcount:  # commit only when something changed — see the note above
            db.commit()
        unread_direct_q = (
            select(func.count())
            .select_from(DirectMessage)
            .where(
                DirectMessage.read_at.is_(None),
                DirectMessage.deleted_at.is_(None),
                DirectMessage.sender_user_id != user.user_id,
                DirectMessage.conversation_id.in_(mine),
            )
            .scalar_subquery()
        )
    else:
        unread_direct_q = literal(0)

    if user.role == "PARENT":
        unread_messages_q = (
            select(func.count())
            .select_from(Message)
            .where(
                Message.parent_user_id == user.user_id,
                Message.sender_role == MessageSenderRole.STAFF,
                Message.read_by_parent_at.is_(None),
            )
            .scalar_subquery()
        )
    else:
        unread_messages_q = literal(0)

    groups_q = unread_class_groups_subquery(user.user_id, class_ids) if class_ids else literal(0)
    mentions_q = (
        select(func.count())
        .select_from(ClassGroupMention)
        .where(ClassGroupMention.mentioned_user_id == user.user_id, ClassGroupMention.seen_at.is_(None))
        .scalar_subquery()
    )
    reports_q = (
        select(func.count()).select_from(DirectReport).where(DirectReport.status == "OPEN").scalar_subquery()
        if user.role == "SCHOOL_ADMIN"
        else literal(0)
    )

    unread_messages, groups, mentions, unread_direct, open_reports = db.execute(
        select(unread_messages_q, groups_q, mentions_q, unread_direct_q, reports_q)
    ).one()

    return AllNotificationsSummary(
        unread_messages=unread_messages,
        unread_class_group_messages=groups,
        unread_mentions=mentions,
        unread_direct_messages=unread_direct,
        open_chat_reports=open_reports,
        total=unread_messages + groups + unread_direct,
    )


@router.get("/mentions", response_model=list[MentionNotification])
def list_mentions(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    _school_id: str = Depends(get_school_scope),
):
    rows = db.execute(
        select(ClassGroupMention, ClassGroupMessage, User.full_name, SchoolClass.name)
        .join(ClassGroupMessage, ClassGroupMessage.id == ClassGroupMention.message_id)
        .join(User, User.id == ClassGroupMessage.sender_user_id)
        .join(SchoolClass, SchoolClass.id == ClassGroupMention.class_id)
        .where(ClassGroupMention.mentioned_user_id == user.user_id)
        .order_by(ClassGroupMention.created_at.desc())
        .limit(30)
    ).all()
    return [
        MentionNotification(
            id=mn.id,
            class_id=mn.class_id,
            class_name=class_name,
            message_id=mn.message_id,
            sender_name=sender_name,
            preview=(msg.body[:140] if msg.body else ("📷 Photo" if msg.attachment_key else "")),
            created_at=mn.created_at,
            seen=mn.seen_at is not None,
        )
        for mn, msg, sender_name, class_name in rows
    ]


@router.post("/mentions/seen")
def mark_mentions_seen(
    data: MarkMentionsSeenRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    _school_id: str = Depends(get_school_scope),
):
    stmt = (
        ClassGroupMention.__table__.update()
        .where(ClassGroupMention.mentioned_user_id == user.user_id, ClassGroupMention.seen_at.is_(None))
        .values(seen_at=func.clock_timestamp())
    )
    if data.ids is not None:
        stmt = stmt.where(ClassGroupMention.id.in_(data.ids))
    db.execute(stmt)
    db.commit()
    return {"ok": True}

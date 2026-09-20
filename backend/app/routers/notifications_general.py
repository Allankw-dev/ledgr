from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func, update
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
from app.routers.class_groups import unread_class_group_count_for_user, mark_class_groups_delivered
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
    turns a sender's single grey tick into two (delivered)."""
    mark_class_groups_delivered(db, user, school_id)

    unread_messages = 0
    if user.role == "PARENT":
        unread_messages = db.execute(
            select(func.count())
            .select_from(Message)
            .where(
                Message.parent_user_id == user.user_id,
                Message.sender_role == MessageSenderRole.STAFF,
                Message.read_by_parent_at.is_(None),
            )
        ).scalar_one()

    groups = unread_class_group_count_for_user(db, user, school_id)
    mentions = db.execute(
        select(func.count())
        .select_from(ClassGroupMention)
        .where(ClassGroupMention.mentioned_user_id == user.user_id, ClassGroupMention.seen_at.is_(None))
    ).scalar_one()

    unread_direct = 0
    if user.role in ("TEACHER", "PARENT"):
        mine = select(DirectConversation.id).where(
            (DirectConversation.teacher_user_id == user.user_id) | (DirectConversation.parent_user_id == user.user_id)
        )
        # The person's app just reached the server: their incoming private messages are now "delivered".
        db.execute(
            update(DirectMessage)
            .where(
                DirectMessage.delivered_at.is_(None),
                DirectMessage.sender_user_id != user.user_id,
                DirectMessage.conversation_id.in_(mine),
            )
            .values(delivered_at=func.clock_timestamp())
        )
        db.commit()
        unread_direct = db.execute(
            select(func.count())
            .select_from(DirectMessage)
            .where(
                DirectMessage.read_at.is_(None),
                DirectMessage.deleted_at.is_(None),
                DirectMessage.sender_user_id != user.user_id,
                DirectMessage.conversation_id.in_(mine),
            )
        ).scalar_one()

    open_reports = 0
    if user.role == "SCHOOL_ADMIN":
        open_reports = db.execute(
            select(func.count()).select_from(DirectReport).where(DirectReport.status == "OPEN")
        ).scalar_one()

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

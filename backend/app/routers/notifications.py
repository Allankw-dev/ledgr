from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, CurrentUser
from app.core.rate_limit import limiter
from app.schemas.notification import NotificationSummary
from app.models.message import Message
from app.models.enums import MessageSenderRole
from app.routers.class_groups import unread_class_group_count_for_user

router = APIRouter(prefix="/api/parent/notifications", tags=["notifications"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=NotificationSummary)
@limiter.limit("60/minute")
def get_notification_summary(
    request: Request,
    db: Session = Depends(get_db),
    school_id: str = Depends(get_school_scope),
    user: CurrentUser = Depends(get_current_user),
):
    """Read-only — meant to be polled from the UI every so often to drive
    the unread badge (nav dot, browser tab title, and the OS-level PWA app
    icon badge). Deliberately never marks anything as read itself; opening
    the actual conversation or class group thread is what does that (see
    messages.py and class_groups.py) — a badge that cleared itself just by
    existing on screen would be useless."""
    if user.role != "PARENT":
        raise HTTPException(403, "This endpoint is for parent accounts only")

    unread_messages = db.execute(
        select(func.count())
        .select_from(Message)
        .where(
            Message.parent_user_id == user.user_id,
            Message.sender_role == MessageSenderRole.STAFF,
            Message.read_by_parent_at.is_(None),
        )
    ).scalar_one()

    unread_class_groups = unread_class_group_count_for_user(db, user, school_id)

    return NotificationSummary(
        unread_messages=unread_messages,
        unread_class_group_messages=unread_class_groups,
        total=unread_messages + unread_class_groups,
    )

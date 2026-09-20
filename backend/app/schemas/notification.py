from datetime import datetime

from pydantic import BaseModel


class NotificationSummary(BaseModel):
    unread_messages: int
    unread_class_group_messages: int
    total: int


class AllNotificationsSummary(BaseModel):
    """For every role (parents, teachers, school office)."""

    unread_messages: int = 0  # parent <-> school 1:1 messages (parents only)
    unread_class_group_messages: int = 0
    unread_mentions: int = 0  # unseen @mentions — a subset of the group messages above
    total: int = 0


class MentionNotification(BaseModel):
    id: str
    class_id: str
    class_name: str
    message_id: str
    sender_name: str
    preview: str
    created_at: datetime
    seen: bool


class MarkMentionsSeenRequest(BaseModel):
    ids: list[str] | None = None  # None/omitted = mark all

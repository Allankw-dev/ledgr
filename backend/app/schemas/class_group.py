from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ClassGroupSummary(BaseModel):
    class_id: str
    class_name: str
    last_message_preview: str | None = None
    last_message_at: datetime | None = None
    unread_count: int = 0
    unread_mentions: int = 0


class SendClassGroupMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    mention_user_ids: list[str] = Field(default_factory=list, max_length=50)
    mention_all: bool = False


class AttachmentInfo(BaseModel):
    name: str
    mime: str
    size: int
    is_image: bool


class MentionInfo(BaseModel):
    user_id: str
    name: str


class ClassGroupMessageResponse(BaseModel):
    id: str
    class_id: str
    sender_user_id: str
    sender_name: str
    sender_role: str
    # e.g. "Parent of Kevin" — helps tell parents apart in a big group.
    sender_subtitle: str | None = None
    body: str
    created_at: datetime
    attachment: AttachmentInfo | None = None
    mentions: list[MentionInfo] = []
    mentions_me: bool = False
    # Only set on the viewer's own messages: sent (1 grey tick), delivered
    # (2 grey ticks), read (2 blue ticks — read by EVERYONE else in the group).
    status: Literal["sent", "delivered", "read"] | None = None
    read_count: int | None = None
    delivered_count: int | None = None
    recipient_count: int | None = None


class AttachmentUrlResponse(BaseModel):
    url: str
    name: str
    mime: str
    size: int
    is_image: bool
    expires_in: int


class GroupMember(BaseModel):
    user_id: str
    name: str
    role: str
    subtitle: str | None = None


class MessageReceipt(BaseModel):
    user_id: str
    name: str
    role: str
    subtitle: str | None = None
    read: bool
    delivered: bool

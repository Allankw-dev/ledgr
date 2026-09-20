from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DirectContact(BaseModel):
    """Someone this person is allowed to start a private chat with."""

    user_id: str
    name: str
    subtitle: str
    conversation_id: str | None = None
    unread_count: int = 0


class DirectConversationOut(BaseModel):
    id: str
    other_user_id: str
    other_name: str
    other_role: str
    other_subtitle: str
    last_message_preview: str | None = None
    last_message_at: datetime | None = None
    unread_count: int = 0
    # False once the two of them no longer have a teacher<->child link (e.g. the
    # teacher was unassigned from the grade): history stays readable, sending stops.
    can_send: bool = True


class StartConversationRequest(BaseModel):
    user_id: str


class SendDirectMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class DirectMessageOut(BaseModel):
    id: str
    conversation_id: str
    sender_user_id: str
    body: str
    created_at: datetime
    # Only on your own messages: sent / delivered (their app fetched it) / read.
    status: Literal["sent", "delivered", "read"] | None = None

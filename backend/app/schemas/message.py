from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    student_id: str | None = None  # optional context: which child this is about


class MessageOut(BaseModel):
    id: str
    sender_role: str
    sender_name: str
    body: str
    student_id: str | None
    student_name: str | None
    created_at: str
    # Whether the OTHER side has read this message yet — i.e. read_by_staff_at
    # for a PARENT-sent message, read_by_parent_at for a STAFF-sent one. Only
    # meaningful for the sender's own messages; drives the WhatsApp-style
    # tick: no timestamp = single grey tick (sent), timestamp set = double
    # blue tick (read). There's no separate "delivered" state tracked here —
    # opening the conversation is the same DB write as marking it read, so
    # unlike WhatsApp's three states, this system only has two honest ones.
    read_at: str | None = None


class ConversationSummary(BaseModel):
    """One row in the staff inbox — one per parent who has messaged."""

    parent_user_id: str
    parent_name: str
    last_message_body: str
    last_message_at: str
    last_message_sender_role: str
    unread_count: int


class TypingStatusOut(BaseModel):
    other_typing: bool

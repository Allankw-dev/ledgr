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


class ConversationSummary(BaseModel):
    """One row in the staff inbox — one per parent who has messaged."""

    parent_user_id: str
    parent_name: str
    last_message_body: str
    last_message_at: str
    last_message_sender_role: str
    unread_count: int

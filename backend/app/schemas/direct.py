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
    blocked: bool = False  # blocked by you


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
    # teacher was unassigned from the grade) or a block is in place: history
    # stays readable, sending stops.
    can_send: bool = True
    blocked_by_me: bool = False


class StartConversationRequest(BaseModel):
    user_id: str


class SendDirectMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class DirectAttachmentInfo(BaseModel):
    name: str
    mime: str
    size: int
    is_image: bool


class DirectMessageOut(BaseModel):
    id: str
    conversation_id: str
    sender_user_id: str
    body: str
    created_at: datetime
    attachment: DirectAttachmentInfo | None = None
    deleted: bool = False
    # Only on your own messages: sent / delivered (their app fetched it) / read.
    status: Literal["sent", "delivered", "read"] | None = None


class BlockRequest(BaseModel):
    user_id: str


ReportCategory = Literal["HARASSMENT", "INAPPROPRIATE", "SPAM", "SAFETY_CONCERN", "OTHER"]
ReportStatus = Literal["OPEN", "REVIEWING", "RESOLVED", "DISMISSED"]


class ReportRequest(BaseModel):
    category: ReportCategory
    details: str | None = Field(default=None, max_length=2000)


class ReportPerson(BaseModel):
    id: str
    name: str
    role: str


class ReportSummary(BaseModel):
    id: str
    created_at: datetime
    status: ReportStatus
    category: ReportCategory
    reporter: ReportPerson
    reported: ReportPerson
    resolved_at: datetime | None = None


class ReportEvidenceMessage(BaseModel):
    sender_name: str
    sender_is_reported: bool
    sent_at: datetime
    body: str
    attachment_name: str | None = None
    deleted_before_report: bool = False


class ReportDetail(ReportSummary):
    details: str | None = None
    evidence: list[ReportEvidenceMessage]
    resolution_note: str | None = None


class UpdateReportRequest(BaseModel):
    status: ReportStatus
    resolution_note: str | None = Field(default=None, max_length=2000)

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterParentRequest(BaseModel):
    full_name: str = Field(min_length=2)
    email: EmailStr
    password: str = Field(min_length=8)


class StudentLookupResult(BaseModel):
    """Deliberately minimal — a name, class, and school is enough for a
    parent to recognize their own child, but reveals nothing financial and
    nothing useful to someone probing for valid admission numbers."""
    student_id: str
    full_name: str
    class_name: str | None
    school_name: str


class RequestLinkPayload(BaseModel):
    relationship_type: str = Field(min_length=2, examples=["mother", "father", "guardian"])


class PendingGuardianRequest(BaseModel):
    id: str
    student_id: str
    student_name: str
    parent_name: str
    parent_email: str
    relationship_type: str
    requested_at: datetime


class GuardianReviewResponse(BaseModel):
    status: str


class ReminderRecipientResult(BaseModel):
    guardian_email: str | None
    guardian_phone: str | None
    email_sent: bool
    sms_sent: bool
    errors: list[str]


class SendReminderResponse(BaseModel):
    recipients_notified: int
    results: list[ReminderRecipientResult]

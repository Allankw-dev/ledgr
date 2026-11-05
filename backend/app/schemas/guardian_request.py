from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.passwords import NewPassword


class RegisterParentRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: str = Field(min_length=7, description="e.g. +254712345678", max_length=32)
    password: NewPassword
    # Both must be true. Ledgr holds a child's name, class and fee records, so the person signing up has to confirm
    # they are an adult and the child's parent or guardian, and that they accept the Terms and Privacy Policy.
    accept_terms: bool = False
    confirm_guardian: bool = False


class StudentLookupResult(BaseModel):
    """Deliberately minimal — a name, class, and school is enough for a
    parent to recognize their own child, but reveals nothing financial and
    nothing useful to someone probing for valid admission numbers."""
    student_id: str
    full_name: str
    class_name: str | None
    school_name: str
    # True when the school already has this signed-in user's phone number
    # (or email) on file as this student's guardian — confirming will
    # connect them right away instead of going to the bursar for review.
    pre_authorized: bool = False


class RequestLinkPayload(BaseModel):
    relationship_type: str = Field(min_length=2, examples=["mother", "father", "guardian"], max_length=40)


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

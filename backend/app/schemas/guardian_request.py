from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterParentRequest(BaseModel):
    full_name: str = Field(min_length=2)
    email: EmailStr
    phone: str = Field(min_length=7, description="e.g. 0712 345 678 or +254712345678")
    password: str = Field(min_length=8)
    admission_number: str = Field(min_length=1, description="Your child's admission number")


class StudentLookupResult(BaseModel):
    """Deliberately minimal — a name, class, and school is enough for a
    parent to recognize their own child, but reveals nothing financial and
    nothing useful to someone probing for valid admission numbers."""
    student_id: str
    full_name: str
    class_name: str | None
    school_name: str
    # True when the school already has this signed-in user's name + phone
    # on file as this student's guardian — confirming will connect them
    # right away instead of going to the bursar for review.
    pre_authorized: bool = False


class RequestLinkPayload(BaseModel):
    relationship_type: str = Field(min_length=2, examples=["mother", "father", "guardian"])


class PendingGuardianRequest(BaseModel):
    id: str
    student_id: str
    student_name: str
    parent_name: str
    parent_email: str
    parent_phone: str | None
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

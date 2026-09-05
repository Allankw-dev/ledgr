from pydantic import BaseModel, Field


class SendAnnouncementRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=150)
    message: str = Field(min_length=1, max_length=2000)
    class_id: str | None = None  # None = every active student in the school


class SendAnnouncementResponse(BaseModel):
    recipient_count: int
    emails_sent: int
    sms_sent: int
    errors: list[str]

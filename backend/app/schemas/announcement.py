from pydantic import BaseModel, Field


class SendAnnouncementRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=150)
    message: str = Field(min_length=1, max_length=2000)
    class_id: str | None = None  # a single grade (kept for older clients)
    # One or more grades. Empty/omitted (and no class_id) = every active student in the school.
    class_ids: list[str] = Field(default_factory=list, max_length=100)

    def target_class_ids(self) -> list[str]:
        ids = list(dict.fromkeys([*self.class_ids, *([self.class_id] if self.class_id else [])]))
        return ids


class SendAnnouncementResponse(BaseModel):
    recipient_count: int
    emails_sent: int
    sms_sent: int
    errors: list[str]

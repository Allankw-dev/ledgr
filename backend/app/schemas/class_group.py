from datetime import datetime

from pydantic import BaseModel, Field


class ClassGroupSummary(BaseModel):
    class_id: str
    class_name: str
    last_message_preview: str | None = None
    last_message_at: datetime | None = None


class SendClassGroupMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class ClassGroupMessageResponse(BaseModel):
    id: str
    class_id: str
    sender_user_id: str
    sender_name: str
    sender_role: str
    body: str
    created_at: datetime

from pydantic import BaseModel


class NotificationSummary(BaseModel):
    unread_messages: int
    unread_class_group_messages: int
    total: int

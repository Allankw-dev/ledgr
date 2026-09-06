from datetime import datetime

from pydantic import BaseModel


class AutomationSettingsResponse(BaseModel):
    enabled: bool


class UpdateAutomationSettingsRequest(BaseModel):
    enabled: bool


class SweepResultResponse(BaseModel):
    invoices_checked: int
    reminders_sent: int
    errors: list[str]


class ReminderLogEntry(BaseModel):
    student_name: str
    tier: int
    sent_at: datetime

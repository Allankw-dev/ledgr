from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

BucketKey = Literal["current", "1-30", "31-60", "61-90", "90+"]


class AgingBucket(BaseModel):
    key: BucketKey
    label: str
    count: int
    amount: Decimal


class AgingRow(BaseModel):
    invoice_id: str
    student_id: str
    student_name: str
    admission_number: str
    class_name: str | None
    term_name: str | None
    due_date: datetime
    days_overdue: int  # 0 or less = not due yet
    balance: Decimal
    bucket: BucketKey


class AgingReport(BaseModel):
    buckets: list[AgingBucket]  # always all five, in order, even when empty
    total_count: int
    total_outstanding: Decimal
    rows: list[AgingRow]  # worst first; capped (see `truncated`)
    truncated: bool

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PaymentAnomalyResponse(BaseModel):
    payment_id: str
    student_id: str
    amount: Decimal
    paid_at: datetime | None
    reasons: list[str]
    severity: str

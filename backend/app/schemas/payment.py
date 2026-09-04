from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import PaymentMethod


class RecordPaymentRequest(BaseModel):
    student_id: str
    invoice_id: str | None = None
    amount: Decimal = Field(gt=0)
    method: PaymentMethod
    reference_code: str | None = None


class ReversePaymentRequest(BaseModel):
    reason: str = Field(min_length=3)


class PaymentResponse(BaseModel):
    id: str
    student_id: str
    invoice_id: str | None
    amount: Decimal
    method: PaymentMethod
    status: str
    paid_at: datetime | None = None

    class Config:
        from_attributes = True

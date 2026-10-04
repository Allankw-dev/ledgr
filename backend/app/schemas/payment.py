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


class ApplyPaymentRequest(BaseModel):
    invoice_id: str


class UnallocatedInvoiceOption(BaseModel):
    id: str
    label: str
    due_date: datetime | None = None
    balance: Decimal


class UnallocatedPaymentResponse(BaseModel):
    """Money that arrived but has no invoice to sit against (the invoices were all
    paid off before an M-Pesa prompt was answered, say). Needs a bursar's decision."""

    id: str
    student_id: str
    student_name: str
    admission_number: str
    amount: Decimal
    method: str
    reference_code: str | None = None
    paid_at: datetime | None = None
    notes: str | None = None
    open_invoices: list[UnallocatedInvoiceOption]

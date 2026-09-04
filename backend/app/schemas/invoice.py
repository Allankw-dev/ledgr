from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class GenerateInvoiceRequest(BaseModel):
    student_id: str
    term_id: str
    due_date: datetime


class BulkGenerateRequest(BaseModel):
    term_id: str
    class_id: str | None = None
    due_date: datetime


class BulkGenerateResult(BaseModel):
    created: int
    skipped: int
    errors: list[dict]


class InvoiceResponse(BaseModel):
    id: str
    student_id: str
    term_id: str
    total_amount: Decimal
    amount_paid: Decimal
    due_date: datetime
    status: str

    class Config:
        from_attributes = True

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


class InvoiceListItem(InvoiceResponse):
    """Same as InvoiceResponse but with the student/class names already
    joined in, so a paginated list page doesn't also need to fetch every
    student just to display who each invoice belongs to."""

    student_name: str
    class_name: str
    has_active_payment_plan: bool = False


class UpdateInvoiceRequest(BaseModel):
    # Deliberately narrow: due_date is the one field safe to correct after
    # the fact without touching money already recorded against the invoice.
    # Amount/items aren't editable here — void and reissue instead if those
    # are wrong, so amount_paid can never end up out of sync with reality.
    due_date: datetime

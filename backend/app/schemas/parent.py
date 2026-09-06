from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ParentPaymentView(BaseModel):
    id: str
    amount: Decimal
    method: str
    paid_at: datetime | None


class ParentInvoiceItemView(BaseModel):
    name: str
    category: str
    amount: Decimal


class ParentInvoiceView(BaseModel):
    id: str
    total_amount: Decimal
    amount_paid: Decimal
    due_date: datetime
    status: str
    items: list[ParentInvoiceItemView] = []
    payments: list[ParentPaymentView] = []


class ParentStudentView(BaseModel):
    """
    Everything a parent is allowed to see about their own child — deliberately
    a narrower shape than the bursar's StudentResponse, which also exposes
    admin-only fields. Never reuse the admin schema here.
    """
    id: str
    full_name: str
    admission_number: str
    class_name: str | None
    invoices: list[ParentInvoiceView]
    balance_due: Decimal

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class InstallmentResponse(BaseModel):
    amount: Decimal
    due_date: datetime


class PaymentPlanResponse(BaseModel):
    installments: list[InstallmentResponse]
    rationale: str


class TrackedInstallment(BaseModel):
    sequence: int
    amount: Decimal
    due_date: datetime
    paid: bool


class TrackedPaymentPlan(BaseModel):
    id: str
    status: str
    rationale: str
    installments: list[TrackedInstallment]

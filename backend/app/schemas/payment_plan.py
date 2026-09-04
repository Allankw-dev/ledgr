from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class InstallmentResponse(BaseModel):
    amount: Decimal
    due_date: datetime


class PaymentPlanResponse(BaseModel):
    installments: list[InstallmentResponse]
    rationale: str

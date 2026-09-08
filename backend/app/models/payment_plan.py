"""
Persisted payment plans — turns payment_plan_service.recommend_payment_plan
from a stateless suggestion into something a parent can actually accept and
track. The recommendation logic itself is untouched; this only adds the
"a parent said yes to this schedule" and "here's progress against it" layer
on top.

Installment "paid" status is deliberately NOT a stored boolean — it's
computed from the invoice's running amount_paid against each installment's
cumulative position (see payment_plan_service.get_installment_progress).
That keeps it correct automatically regardless of how a payment is made
(M-Pesa, manual, doesn't need to be tagged to a specific installment) and
however unevenly a parent actually pays against the schedule.
"""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.school import gen_uuid


class PaymentPlanStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class PaymentPlan(Base):
    """One accepted installment schedule for one invoice. At most one
    ACTIVE plan per invoice — see payment_plan_service.create_payment_plan,
    which enforces that rather than a DB constraint, since a CANCELLED or
    COMPLETED plan should stay in history alongside a new one."""

    __tablename__ = "payment_plans"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    status: Mapped[PaymentPlanStatus] = mapped_column(
        SAEnum(PaymentPlanStatus), nullable=False, default=PaymentPlanStatus.ACTIVE
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    accepted_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    installments: Mapped[list["PaymentPlanInstallment"]] = relationship(
        back_populates="plan", order_by="PaymentPlanInstallment.sequence", cascade="all, delete-orphan"
    )


class PaymentPlanInstallment(Base):
    __tablename__ = "payment_plan_installments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    plan_id: Mapped[str] = mapped_column(ForeignKey("payment_plans.id"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    plan: Mapped["PaymentPlan"] = relationship(back_populates="installments")

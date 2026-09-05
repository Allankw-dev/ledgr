"""
Tables that exist purely to make a future trained model possible, per the
design note in risk_scoring.py: once a school has accumulated enough
resolved invoices, (InvoiceRiskSnapshot, InvoiceOutcome) joined on
invoice_id is exactly the labeled training set needed to swap the
rules-based scorer for a real one, without changing any caller.

Neither table drives any decision today. They are write-only from the
app's perspective; a future offline training job is the only reader.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.school import gen_uuid


class InvoiceOutcomeLabel(str, enum.Enum):
    PAID_ON_TIME = "PAID_ON_TIME"
    PAID_LATE = "PAID_LATE"
    DEFAULTED = "DEFAULTED"  # cancelled while still unpaid / written off


class InvoiceRiskSnapshot(Base):
    """A risk score exactly as it was shown to a human (dashboard or AI
    assistant), at the moment it was shown. Written from
    analytics_service.get_top_risk_invoices — not from every internal call
    to compute_risk_score — so this table reflects only scores someone
    actually saw, which is what later calibration analysis needs."""

    __tablename__ = "invoice_risk_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    history_score: Mapped[float] = mapped_column(Float, nullable=False)
    overdue_score: Mapped[float] = mapped_column(Float, nullable=False)
    balance_score: Mapped[float] = mapped_column(Float, nullable=False)
    reversal_score: Mapped[float] = mapped_column(Float, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String, nullable=False)


class InvoiceOutcome(Base):
    """What actually happened to an invoice, set exactly once — the first
    time it reaches a terminal state. Not updated after that: if something
    downstream later edits a resolved invoice, this keeps recording what
    actually happened the first time it resolved, since that's the real
    training label."""

    __tablename__ = "invoice_outcomes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), nullable=False, unique=True, index=True)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    outcome: Mapped[InvoiceOutcomeLabel] = mapped_column(SAEnum(InvoiceOutcomeLabel), nullable=False)
    days_late: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

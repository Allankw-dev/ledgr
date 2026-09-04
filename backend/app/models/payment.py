from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, ForeignKey, func, Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.school import gen_uuid
from app.models.enums import PaymentMethod, PaymentStatus
from app.models.invoice import MONEY


class Payment(Base):
    """
    Append-only ledger of money actually received. Rows are never edited or
    deleted once CONFIRMED — corrections happen via a linked reversal row
    (see payment_service.reverse_payment), so the ledger is always auditable.
    """

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.id"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(SAEnum(PaymentMethod), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(SAEnum(PaymentStatus), default=PaymentStatus.PENDING, index=True)
    reference_code: Mapped[str | None] = mapped_column(String, nullable=True)  # M-Pesa code, bank ref
    external_txn_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)  # provider txn id
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_of_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Every meaningful state change gets logged — required for financial
    software, and doubles as training data for anomaly detection later."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "PAYMENT_CONFIRMED"
    entity_type: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "Payment"
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    log_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

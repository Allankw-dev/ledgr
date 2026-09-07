from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, ForeignKey, func, Enum as SAEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.school import gen_uuid
from app.models.enums import MpesaTransactionStatus
from app.models.invoice import MONEY


class MpesaTransaction(Base):
    """
    Every C2B confirmation Safaricom sends when someone pays the school's
    paybill directly (NOT via our own STK push button) — a parent walking
    into an M-Pesa shop, or paying from the M-Pesa menu themselves using
    the child's admission number as the account reference.

    Deliberately school_id-nullable: until a transaction is matched to a
    student, we genuinely don't know which school it belongs to (a single
    paybill can serve students across different schools, and
    admission_number is only unique per school — see match logic in
    mpesa_reconciliation_service.py). Rows are never deleted, matched or
    not, so the raw feed from Safaricom is always fully reconstructable.
    """

    __tablename__ = "mpesa_transactions"
    __table_args__ = (UniqueConstraint("trans_id", name="uq_mpesa_transactions_trans_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    trans_id: Mapped[str] = mapped_column(String, nullable=False, index=True)  # Safaricom's unique receipt code
    trans_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    bill_ref_number: Mapped[str | None] = mapped_column(String, nullable=True)  # what the payer typed — expected to be an admission number
    msisdn: Mapped[str | None] = mapped_column(String, nullable=True)  # payer's phone
    payer_name: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[MpesaTransactionStatus] = mapped_column(
        SAEnum(MpesaTransactionStatus), default=MpesaTransactionStatus.UNMATCHED, index=True
    )
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"), nullable=True, index=True)
    matched_student_id: Mapped[str | None] = mapped_column(ForeignKey("students.id"), nullable=True)
    matched_payment_id: Mapped[str | None] = mapped_column(ForeignKey("payments.id"), nullable=True)
    resolved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

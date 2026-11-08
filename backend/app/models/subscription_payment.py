from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.invoice import MONEY
from app.models.school import gen_uuid


class SubscriptionPayment(Base):
    """
    What a SCHOOL paid the platform operator for using Ledgr. This is the operator's own book, not a school's:
    parents' fee payments live in `payments`. OWNER-ONLY (see sql/enable_rls.sql): the app role cannot read it, and
    only the platform routes, on the system connection, ever do.

    Rows are never edited. A mistake is VOIDED (kept, marked, with a reason) so the history stays honest. Voiding
    does not move the school's paid-until date back: the operator does that deliberately.
    """

    __tablename__ = "subscription_payments"
    __table_args__ = (
        # The same bank or M-Pesa reference can't be booked twice for a school (a double click, or the same
        # payment entered by two people). Voided rows don't count, so a wrong entry can be redone.
        Index(
            "ux_subscription_payments_reference",
            "school_id",
            "reference",
            unique=True,
            postgresql_where=text("reference IS NOT NULL AND voided_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    method: Mapped[str] = mapped_column(String, nullable=False)  # MPESA | BANK_TRANSFER | CASH | CHEQUE | OTHER
    reference: Mapped[str | None] = mapped_column(String, nullable=True)  # M-Pesa code, bank reference
    paid_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    months_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    recorded_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(String, nullable=True)

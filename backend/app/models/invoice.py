from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Numeric, DateTime, ForeignKey, func, Enum as SAEnum, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.school import gen_uuid
from app.models.enums import FeeCategory, InvoiceStatus

# Numeric(12, 2) mirrors Prisma's Decimal(12, 2) — money is never Float here.
MONEY = Numeric(12, 2)


class FeeStructure(Base):
    """The 'price list': what a class owes per term, per category."""

    __tablename__ = "fee_structures"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    term_id: Mapped[str] = mapped_column(ForeignKey("terms.id"), nullable=False)
    class_id: Mapped[str | None] = mapped_column(ForeignKey("school_classes.id"), nullable=True)  # null = all classes
    category: Mapped[FeeCategory] = mapped_column(SAEnum(FeeCategory), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Invoice(Base):
    """One bill per student per term."""

    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    term_id: Mapped[str] = mapped_column(ForeignKey("terms.id"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(MONEY, default=0)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(SAEnum(InvoiceStatus), default=InvoiceStatus.ISSUED, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items: Mapped[list["InvoiceItem"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    fee_structure_id: Mapped[str] = mapped_column(ForeignKey("fee_structures.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    invoice: Mapped["Invoice"] = relationship(back_populates="items")


class InvoiceReminderLog(Base):
    """One row per automated overdue-reminder actually sent — the record
    the escalation logic checks to decide whether an invoice is due for
    its next tier, and the audit trail proving what was auto-sent when."""

    __tablename__ = "invoice_reminder_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 = first notice, 2 = follow-up, 3 = final notice
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

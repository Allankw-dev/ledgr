"""
Smart payment plan recommender.

Same reasoning as risk_scoring.py: with limited real payment history across
the school, a trained model would have nothing meaningful to learn from.
This instead builds a plan from the family's own OBSERVED payment behavior
(the actual sizes of payments they've made before) where that exists, and
falls back to sensible balance-based tiers where it doesn't — always
explainable to a bursar or parent, never a black box. The recommendation
shape here is stable regardless of what computes it, so swapping in a
trained model later doesn't require touching any caller.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.payment_plan import PaymentPlan, PaymentPlanInstallment, PaymentPlanStatus
from app.models.enums import PaymentStatus


@dataclass
class Installment:
    amount: Decimal
    due_date: datetime


@dataclass
class PaymentPlanRecommendation:
    installments: list[Installment]
    rationale: str


def _typical_payment_size(db: Session, student_id: str) -> Decimal | None:
    """Median of this student's past CONFIRMED payment amounts, if any —
    used as a proxy for what size of installment this family can
    realistically manage, based on what they've actually done before."""
    payments = db.execute(
        select(Payment).where(
            Payment.student_id == student_id,
            Payment.status == PaymentStatus.CONFIRMED,
            Payment.amount > 0,  # exclude reversal correction rows (negative amounts)
        )
    ).scalars().all()

    if not payments:
        return None

    amounts = sorted(p.amount for p in payments)
    mid = len(amounts) // 2
    if len(amounts) % 2 == 0:
        return (amounts[mid - 1] + amounts[mid]) / 2
    return amounts[mid]


def _installment_count_for_balance(balance: Decimal) -> int:
    """Fallback tiers when there's no payment history to go on yet."""
    if balance <= Decimal("10000"):
        return 1
    if balance <= Decimal("30000"):
        return 2
    return 3


def recommend_payment_plan(db: Session, student_id: str, invoice_id: str) -> PaymentPlanRecommendation:
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise ValueError("Invoice not found")

    balance = invoice.total_amount - invoice.amount_paid
    if balance <= 0:
        return PaymentPlanRecommendation(installments=[], rationale="This invoice is already fully paid.")

    now = datetime.now(timezone.utc)
    typical = _typical_payment_size(db, student_id)

    if typical and typical > 0:
        count = min(4, max(1, math.ceil(balance / typical)))
        rationale = (
            f"Based on this family's past payments (typically around KES {typical:,.0f} each), "
            f"split into {count} installment{'s' if count > 1 else ''} of a similar size."
        )
    else:
        count = _installment_count_for_balance(balance)
        rationale = (
            f"No payment history yet for this family, so this uses a standard {count}-installment "
            f"plan sized to the balance."
        )

    # Spread installments evenly between now and the due date. If the due
    # date has already passed, compress into weekly installments starting
    # immediately instead of backdating anything.
    if invoice.due_date > now:
        span_days = max(1, (invoice.due_date - now).days)
    else:
        span_days = 7 * count  # weekly cadence when already overdue

    step_days = max(1, span_days // count)

    # Split the balance into `count` roughly-equal amounts that sum EXACTLY
    # to the balance (the last installment absorbs any rounding remainder —
    # a bursar reconciling this against the invoice total should never see
    # a one-cent mismatch).
    base_amount = (balance / count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    installments = []
    running_total = Decimal("0")
    for i in range(count):
        if i == count - 1:
            amount = balance - running_total  # absorb rounding remainder
        else:
            amount = base_amount
            running_total += amount

        due = now + timedelta(days=step_days * (i + 1)) if invoice.due_date > now else now + timedelta(days=7 * (i + 1))
        installments.append(Installment(amount=amount, due_date=due))

    return PaymentPlanRecommendation(installments=installments, rationale=rationale)


@dataclass
class InstallmentProgress:
    sequence: int
    amount: Decimal
    due_date: datetime
    paid: bool


def get_active_plan(db: Session, invoice_id: str) -> PaymentPlan | None:
    return db.execute(
        select(PaymentPlan).where(PaymentPlan.invoice_id == invoice_id, PaymentPlan.status == PaymentPlanStatus.ACTIVE)
    ).scalar_one_or_none()


def create_payment_plan(db: Session, invoice_id: str, actor_user_id: str | None = None) -> PaymentPlan:
    """Turns the stateless recommendation into something trackable. Only
    one ACTIVE plan per invoice at a time — accepting a new one implicitly
    means the parent wants to replace whatever plan (if any) they'd
    accepted before, not run two in parallel."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    balance = invoice.total_amount - invoice.amount_paid
    if balance <= 0:
        raise HTTPException(400, "This invoice is already fully paid — no payment plan needed.")

    existing = get_active_plan(db, invoice_id)
    if existing:
        existing.status = PaymentPlanStatus.CANCELLED

    recommendation = recommend_payment_plan(db, invoice.student_id, invoice_id)
    if not recommendation.installments:
        raise HTTPException(400, "No payment plan could be generated for this invoice.")

    plan = PaymentPlan(
        invoice_id=invoice_id,
        student_id=invoice.student_id,
        school_id=invoice.school_id,
        status=PaymentPlanStatus.ACTIVE,
        rationale=recommendation.rationale,
        accepted_by_user_id=actor_user_id,
    )
    db.add(plan)
    db.flush()

    for i, installment in enumerate(recommendation.installments):
        db.add(
            PaymentPlanInstallment(
                plan_id=plan.id,
                sequence=i,
                amount=installment.amount,
                due_date=installment.due_date,
            )
        )

    db.commit()
    db.refresh(plan)
    return plan


def cancel_payment_plan(db: Session, plan: PaymentPlan) -> PaymentPlan:
    plan.status = PaymentPlanStatus.CANCELLED
    db.commit()
    db.refresh(plan)
    return plan


def get_installment_progress(db: Session, plan: PaymentPlan) -> list[InstallmentProgress]:
    """An installment counts as paid once the invoice's cumulative
    amount_paid reaches the running total through that installment's
    position — not by tagging individual payments to individual
    installments, which would break the moment a parent pays an amount
    that doesn't line up exactly with the schedule (which is common: they
    round up, or pay in one lump sum instead of on schedule)."""
    invoice = db.get(Invoice, plan.invoice_id)
    amount_paid = invoice.amount_paid if invoice else Decimal("0")

    progress = []
    running_total = Decimal("0")
    for installment in plan.installments:
        running_total += installment.amount
        progress.append(
            InstallmentProgress(
                sequence=installment.sequence,
                amount=installment.amount,
                due_date=installment.due_date,
                paid=amount_paid >= running_total,
            )
        )

    # If every installment is now covered by what's actually been paid,
    # the plan has done its job — mark it COMPLETED so it stops showing as
    # an open commitment, without needing a separate sync job to notice.
    if plan.status == PaymentPlanStatus.ACTIVE and all(p.paid for p in progress):
        plan.status = PaymentPlanStatus.COMPLETED
        db.commit()

    return progress

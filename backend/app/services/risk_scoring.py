"""
Payment default risk scoring.

WHY RULES-BASED, NOT MACHINE LEARNED: a real ML model (logistic regression,
gradient boosting, etc.) needs a meaningful volume of historical outcomes to
learn from — a handful of test payments would just let it memorize noise
and report false confidence. This scores on four transparent, explainable
factors instead, each independently defensible to a bursar who has to trust
the number. Once a school has accumulated enough real payment history
(realistically: a few hundred resolved invoices across multiple terms),
`compute_risk_score`'s return shape (features breakdown + score) is exactly
the training data a real model would need — swap this function's internals
for a trained model without touching any caller, since the interface stays
the same.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.enums import InvoiceStatus, PaymentStatus


@dataclass
class RiskFactors:
    history_score: float  # 0-40: based on this student's track record on past invoices
    overdue_score: float  # 0-30: how overdue THIS invoice is, if at all
    balance_score: float  # 0-20: how much of THIS invoice remains unpaid
    reversal_score: float  # 0-10: history of reversed/failed payments
    total: float = field(init=False)

    def __post_init__(self):
        self.total = round(
            self.history_score + self.overdue_score + self.balance_score + self.reversal_score, 1
        )


@dataclass
class RiskAssessment:
    score: float  # 0-100
    level: str  # "low" | "medium" | "high"
    factors: RiskFactors
    explanation: str


def _risk_level(score: float) -> str:
    if score >= 61:
        return "high"
    if score >= 31:
        return "medium"
    return "low"


def compute_risk_score(db: Session, student_id: str, invoice_id: str) -> RiskAssessment:
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise ValueError("Invoice not found")

    past_invoices = db.execute(
        select(Invoice).where(
            Invoice.student_id == student_id,
            Invoice.id != invoice_id,
        )
    ).scalars().all()

    problem_payments = db.execute(
        select(Payment).where(
            Payment.student_id == student_id,
            Payment.status.in_([PaymentStatus.REVERSED, PaymentStatus.FAILED]),
        )
    ).scalars().all()

    return _score_from_data(invoice, past_invoices, len(problem_payments))


def compute_risk_scores_batch(db: Session, invoices: list[Invoice]) -> dict[str, RiskAssessment]:
    """
    Same scoring as compute_risk_score, for many invoices at once without
    paying for it per-invoice. compute_risk_score does 2 DB round-trips
    per call — fine in isolation (e.g. the single-invoice /risk endpoint),
    but get_top_risk_invoices used to call it in a loop over up to 30
    candidates, meaning up to ~60 sequential round-trips on every
    dashboard load. This does the same 2 queries ONCE, with an IN clause
    across every candidate's student_id, then scores each invoice from
    data already in memory.
    """
    if not invoices:
        return {}

    student_ids = list({inv.student_id for inv in invoices})

    all_past_invoices = db.execute(
        select(Invoice).where(Invoice.student_id.in_(student_ids))
    ).scalars().all()
    past_by_student: dict[str, list[Invoice]] = {}
    for inv in all_past_invoices:
        past_by_student.setdefault(inv.student_id, []).append(inv)

    all_problem_payments = db.execute(
        select(Payment.student_id).where(
            Payment.student_id.in_(student_ids),
            Payment.status.in_([PaymentStatus.REVERSED, PaymentStatus.FAILED]),
        )
    ).scalars().all()
    problem_count_by_student: dict[str, int] = {}
    for sid in all_problem_payments:
        problem_count_by_student[sid] = problem_count_by_student.get(sid, 0) + 1

    results = {}
    for invoice in invoices:
        # Exclude the invoice itself from its own "past invoices" history,
        # same rule compute_risk_score applies via `Invoice.id != invoice_id`.
        past = [inv for inv in past_by_student.get(invoice.student_id, []) if inv.id != invoice.id]
        problem_count = problem_count_by_student.get(invoice.student_id, 0)
        results[invoice.id] = _score_from_data(invoice, past, problem_count)

    return results


def _score_from_data(invoice: Invoice, past_invoices: list[Invoice], problem_payment_count: int) -> RiskAssessment:
    now = datetime.now(timezone.utc)

    # --- History component (0-40): this student's track record on PAST invoices ---
    if past_invoices:
        problem_count = sum(
            1
            for inv in past_invoices
            if inv.status == InvoiceStatus.OVERDUE
            or (inv.status != InvoiceStatus.PAID and inv.due_date < now)
        )
        late_ratio = problem_count / len(past_invoices)
        history_score = round(late_ratio * 40, 1)
    else:
        # No history yet (new student, or first invoice) — neither penalize
        # nor reward; let the other factors carry the assessment.
        history_score = 15.0

    # --- Overdue component (0-30): how late is THIS invoice, if at all ---
    balance = invoice.total_amount - invoice.amount_paid
    days_overdue = (now - invoice.due_date).days if invoice.due_date < now else 0

    if balance <= 0:
        overdue_score = 0.0
    elif days_overdue > 0:
        overdue_score = min(30.0, days_overdue * 2.0)
    else:
        days_until_due = (invoice.due_date - now).days
        overdue_score = 5.0 if days_until_due <= 3 else 0.0

    # --- Balance component (0-20): proportion of THIS invoice still unpaid,
    # but only counted once the due date is close or passed. An invoice due
    # in three weeks with nothing paid yet isn't risky — that's true of
    # almost every invoice on day one. Only start counting it as the
    # deadline approaches, same threshold as the "due soon" nudge above.
    balance_ratio = float(balance / invoice.total_amount) if invoice.total_amount > 0 else 0.0
    days_until_due = (invoice.due_date - now).days if invoice.due_date > now else 0
    is_near_or_past_due = invoice.due_date < now or days_until_due <= 3
    balance_score = round(max(0.0, min(1.0, balance_ratio)) * 20, 1) if is_near_or_past_due else 0.0

    # --- Reversal component (0-10): history of reversed/failed M-Pesa attempts ---
    reversal_score = min(10.0, problem_payment_count * 5.0)

    factors = RiskFactors(
        history_score=history_score,
        overdue_score=overdue_score,
        balance_score=balance_score,
        reversal_score=reversal_score,
    )

    level = _risk_level(factors.total)

    parts = []
    if factors.history_score >= 20:
        parts.append("a pattern of late/unpaid invoices")
    if factors.overdue_score > 0:
        parts.append(f"{days_overdue} day(s) overdue" if days_overdue > 0 else "due soon with a balance remaining")
    if factors.balance_score >= 15:
        parts.append("most of this invoice still unpaid")
    if factors.reversal_score > 0:
        parts.append("past payment attempts that failed or were reversed")

    explanation = (
        "Driven by: " + ", ".join(parts) + "."
        if parts
        else "No significant risk factors detected for this invoice."
    )

    return RiskAssessment(score=factors.total, level=level, factors=factors, explanation=explanation)

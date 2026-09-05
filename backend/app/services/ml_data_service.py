"""
Training-data logging for a future supervised risk model.

Two independent writes happen here, and neither one trains anything by
itself:
- log_risk_snapshot: the risk score exactly as it was shown to a human.
- log_invoice_outcome_if_resolved: what actually happened to that invoice.

Once a school has enough resolved invoices, join InvoiceOutcome to the most
recent InvoiceRiskSnapshot taken before each invoice's resolved_at (on
invoice_id, filtered to snapshots where taken_at < resolved_at) to build a
labeled training set — that join is exactly the (features, outcome) data
risk_scoring.compute_risk_score's docstring says would let a real model
replace it.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.enums import InvoiceStatus
from app.models.invoice import Invoice
from app.models.ml import InvoiceOutcome, InvoiceOutcomeLabel, InvoiceRiskSnapshot
from app.services.risk_scoring import RiskAssessment


def log_risk_snapshot(db: Session, school_id: str, invoice_id: str, assessment: RiskAssessment) -> None:
    db.add(
        InvoiceRiskSnapshot(
            invoice_id=invoice_id,
            school_id=school_id,
            history_score=assessment.factors.history_score,
            overdue_score=assessment.factors.overdue_score,
            balance_score=assessment.factors.balance_score,
            reversal_score=assessment.factors.reversal_score,
            total_score=assessment.factors.total,
            risk_level=assessment.level,
        )
    )


def log_invoice_outcome_if_resolved(db: Session, invoice: Invoice) -> None:
    """Call after an invoice's status has just been recomputed. No-ops if
    the invoice hasn't reached a terminal state yet, or if an outcome was
    already recorded for it (first resolution wins)."""
    if invoice.status not in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED):
        return

    existing = db.query(InvoiceOutcome).filter(InvoiceOutcome.invoice_id == invoice.id).first()
    if existing:
        return

    if invoice.status == InvoiceStatus.CANCELLED:
        outcome = (
            InvoiceOutcomeLabel.DEFAULTED
            if invoice.amount_paid < invoice.total_amount
            else InvoiceOutcomeLabel.PAID_ON_TIME
        )
        days_late = None
    else:  # PAID
        now = datetime.now(timezone.utc)
        days_late = max(0, (now - invoice.due_date).days)
        outcome = InvoiceOutcomeLabel.PAID_LATE if days_late > 0 else InvoiceOutcomeLabel.PAID_ON_TIME

    db.add(
        InvoiceOutcome(
            invoice_id=invoice.id,
            school_id=invoice.school_id,
            outcome=outcome,
            days_late=days_late,
        )
    )

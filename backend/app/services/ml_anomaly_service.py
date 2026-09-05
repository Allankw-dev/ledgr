"""
Statistical anomaly detection (Isolation Forest) — a second, genuinely
unsupervised ML signal alongside the rule-based checks in
anomaly_detection.py.

Unlike risk_scoring's default-prediction problem, this doesn't need labeled
outcomes: Isolation Forest only needs a distribution of past payments to
judge new ones against, which every school already has as soon as it's
processed a handful of them — no waiting for "enough resolved invoices"
the way a supervised model would.

Fit per-school, per-call rather than as a persisted model file: payment
volume per school is small enough that refitting on the recent window is
cheap, and it means the model always reflects that school's current
patterns instead of a stale snapshot that needs a retraining job.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
from sklearn.ensemble import IsolationForest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import PaymentStatus
from app.models.payment import Payment

# Isolation Forest needs a real distribution to learn from — below this,
# it would just be fitting noise from a handful of points and calling
# whichever one looks slightly different "anomalous".
MIN_PAYMENTS_TO_FIT = 20


@dataclass
class MLAnomalyResult:
    payment_id: str
    student_id: str
    anomaly_score: float  # 0-1, higher = more statistically unusual
    reason: str


def _features(payment: Payment) -> list[float]:
    """Amount, hour-of-day, and day-of-week of the payment — enough for
    Isolation Forest to separate 'a normal payment for this school' from
    an outlier, without needing any labeled example of either."""
    paid_at = payment.paid_at or payment.created_at
    return [float(payment.amount), float(paid_at.hour), float(paid_at.weekday())]


def scan_school_for_ml_anomalies(db: Session, school_id: str, days: int = 90) -> list[MLAnomalyResult]:
    window_start = datetime.now(timezone.utc) - timedelta(days=days)

    payments = db.execute(
        select(Payment).where(
            Payment.school_id == school_id,
            Payment.status == PaymentStatus.CONFIRMED,
            Payment.amount > 0,
            Payment.created_at >= window_start,
        )
    ).scalars().all()

    if len(payments) < MIN_PAYMENTS_TO_FIT:
        return []  # not enough data for the model to have learned a real distribution yet

    X = np.array([_features(p) for p in payments])

    model = IsolationForest(n_estimators=100, contamination="auto", random_state=42)
    model.fit(X)
    raw_scores = model.decision_function(X)  # higher = more normal
    predictions = model.predict(X)  # -1 = anomaly, 1 = normal

    # decision_function's range varies by fit; normalize to a 0-1 "how
    # unusual" score that's meaningful without knowing sklearn internals.
    score_range = raw_scores.max() - raw_scores.min()
    normalized = 1 - (raw_scores - raw_scores.min()) / (score_range + 1e-9)

    results = [
        MLAnomalyResult(
            payment_id=payment.id,
            student_id=payment.student_id,
            anomaly_score=round(float(score), 3),
            reason="Statistically unusual amount/timing compared to this school's recent payment pattern",
        )
        for payment, pred, score in zip(payments, predictions, normalized)
        if pred == -1
    ]
    return sorted(results, key=lambda r: r.anomaly_score, reverse=True)

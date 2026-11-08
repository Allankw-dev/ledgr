"""One row per school describing how its online payments are doing, for the platform operator.

Built from a handful of grouped queries (one per measure, each covering ALL schools), never one query per school,
so the cost grows with the amount of data and not with the number of schools. Counts only: no payer names, phone
numbers or per-person amounts leave this module.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import MpesaTransactionStatus, PaymentMethod, PaymentStatus
from app.models.mpesa_account import SchoolMpesaAccount
from app.models.mpesa_transaction import MpesaTransaction
from app.models.payment import Payment
from app.models.school import School
from app.schemas.subscription import SchoolPaymentsHealth
from app.services.payment_service import MISMATCH_NOTE_PREFIX
from app.services.subscription_service import compute_state

STUCK_AFTER = timedelta(minutes=15)  # a prompt is answered or times out within a minute or two
STUCK_WINDOW = timedelta(days=7)  # only recent ones: old abandoned prompts are not today's problem
FAILED_ALERT_AT = 5  # this many failed prompts in a week is worth a look

_RANK = {"ok": 0, "info": 1, "warn": 2, "bad": 3}


def _grouped(db: Session, *columns, where: list) -> dict[str, tuple]:
    rows = db.execute(select(Payment.school_id, *columns).where(*where).group_by(Payment.school_id)).all()
    return {r[0]: tuple(r[1:]) for r in rows}


def build_payments_health(db: Session, now: datetime | None = None) -> list[SchoolPaymentsHealth]:
    now = now or datetime.now(timezone.utc)
    mpesa = Payment.method == PaymentMethod.MPESA

    schools = db.execute(select(School).order_by(School.name.asc())).scalars().all()
    accounts = {a.school_id: a for a in db.execute(select(SchoolMpesaAccount)).scalars().all()}

    confirmed = _grouped(
        db,
        func.count(),
        func.coalesce(func.sum(Payment.amount), 0),
        func.max(func.coalesce(Payment.paid_at, Payment.created_at)),
        where=[
            mpesa,
            Payment.status == PaymentStatus.CONFIRMED,
            Payment.amount > 0,
            Payment.reversal_of_id.is_(None),
            Payment.created_at >= now - timedelta(days=30),
        ],
    )
    # "Last confirmed" should not stop at 30 days: a school silent for 3 months is exactly what the operator wants to see.
    last_ever = dict(
        db.execute(
            select(Payment.school_id, func.max(func.coalesce(Payment.paid_at, Payment.created_at)))
            .where(mpesa, Payment.status == PaymentStatus.CONFIRMED, Payment.amount > 0, Payment.reversal_of_id.is_(None))
            .group_by(Payment.school_id)
        ).all()
    )
    not_a_mismatch = ~func.coalesce(Payment.notes, "").like(f"{MISMATCH_NOTE_PREFIX}%")
    stuck = _grouped(
        db,
        func.count(),
        where=[
            mpesa,
            Payment.status == PaymentStatus.PENDING,
            not_a_mismatch,
            Payment.created_at < now - STUCK_AFTER,
            Payment.created_at >= now - STUCK_WINDOW,
        ],
    )
    failed = _grouped(
        db, func.count(), where=[mpesa, Payment.status == PaymentStatus.FAILED, Payment.created_at >= now - timedelta(days=7)]
    )
    mismatches = _grouped(
        db,
        func.count(),
        where=[mpesa, Payment.status == PaymentStatus.PENDING, func.coalesce(Payment.notes, "").like(f"{MISMATCH_NOTE_PREFIX}%")],
    )
    unallocated = _grouped(
        db,
        func.count(),
        where=[
            Payment.invoice_id.is_(None),
            Payment.status == PaymentStatus.CONFIRMED,
            Payment.amount > 0,
            Payment.reversal_of_id.is_(None),
        ],
    )
    unmatched = dict(
        db.execute(
            select(MpesaTransaction.school_id, func.count())
            .where(MpesaTransaction.status == MpesaTransactionStatus.UNMATCHED, MpesaTransaction.school_id.is_not(None))
            .group_by(MpesaTransaction.school_id)
        ).all()
    )
    on_global = sum(1 for s in schools if s.mpesa_mode == "GLOBAL")

    out: list[SchoolPaymentsHealth] = []
    for s in schools:
        state = compute_state(s.subscription_status, s.trial_ends_at, s.paid_until)
        acct = accounts.get(s.id)
        c30 = confirmed.get(s.id, (0, Decimal(0), None))
        shared = s.mpesa_mode == "GLOBAL" and on_global > 1

        attention: list[tuple[str, str]] = []  # (severity, text)
        if s.mpesa_mode == "OFF":
            attention.append(("info", "Online M-Pesa is off for this school"))
        if s.mpesa_mode == "OWN" and acct is not None:
            if acct.last_error:
                attention.append(("bad", f"Last Safaricom problem: {acct.last_error}"))
            if acct.c2b_registered_at is None:
                attention.append(("warn", "Direct paybill payments aren't registered with Safaricom yet (prompts still work)"))
        if shared:
            attention.append(("warn", f"Shares the server-wide paybill with {on_global - 1} other school(s)"))
        n_stuck = stuck.get(s.id, (0,))[0]
        if n_stuck:
            attention.append(("warn", f"{n_stuck} payment prompt(s) have been waiting more than 15 minutes"))
        n_failed = failed.get(s.id, (0,))[0]
        if n_failed >= FAILED_ALERT_AT:
            attention.append(("warn", f"{n_failed} failed payment prompts in the last 7 days"))
        n_mis = mismatches.get(s.id, (0,))[0]
        if n_mis:
            attention.append(("warn", f"{n_mis} payment(s) with a different amount are waiting for the bursar"))
        n_unm = unmatched.get(s.id, 0)
        if n_unm:
            attention.append(("warn", f"{n_unm} direct paybill payment(s) could not be matched to a student"))

        severity = max((a[0] for a in attention), key=_RANK.__getitem__, default="ok")
        out.append(
            SchoolPaymentsHealth(
                school_id=s.id,
                school_name=s.name,
                currency=s.currency,
                subscription_status=state.status,  # type: ignore[arg-type]
                read_only=state.read_only,
                mpesa_mode=s.mpesa_mode,  # type: ignore[arg-type]
                environment=acct.environment if acct else None,
                shortcode=acct.shortcode if acct else None,
                tested_at=acct.tested_at if acct else None,
                c2b_registered_at=acct.c2b_registered_at if acct else None,
                last_error=acct.last_error if acct else None,
                confirmed_30d_count=c30[0],
                confirmed_30d_amount=Decimal(c30[1]),
                last_confirmed_at=last_ever.get(s.id),
                stuck_pending=n_stuck,
                failed_7d=n_failed,
                mismatches=n_mis,
                unallocated=unallocated.get(s.id, (0,))[0],
                unmatched_c2b=n_unm,
                shared_paybill=shared,
                severity=severity,  # type: ignore[arg-type]
                attention=[a[1] for a in sorted(attention, key=lambda a: -_RANK[a[0]])],
            )
        )
    out.sort(key=lambda r: (-_RANK[r.severity], r.school_name.lower()))
    return out

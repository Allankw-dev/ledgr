"""Handlers for the durable job queue (core/jobs.py).

Design rule: one job per delivery CHANNEL per recipient. If the SMS provider is
down, only the SMS job retries — the email that already went out is never
re-sent. Fan-out jobs use dedupe keys so a re-run enqueues nothing twice.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.core.database import SystemSessionLocal
from app.core.jobs import enqueue, job_handler
from app.models.enums import GuardianLinkStatus
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.school import School, User
from app.models.student import Student, StudentGuardian
from app.services.notification_service import (
    NotificationConfigError,
    compose_payment_confirmation,
    compose_payment_failed,
    send_email,
    send_sms,
)

logger = logging.getLogger(__name__)

PLACEHOLDER_EMAIL_DOMAIN = "@phone.ledgr.invalid"


def enqueue_guardian_message(
    db,
    *,
    school_id: str,
    guardian_id: str,
    email_subject: str,
    email_body: str,
    sms_text: str,
    dedupe_prefix: str,
) -> int:
    """Queue the email + SMS jobs for one guardian (contact details are looked up
    when the job runs, so they aren't copied into the queue). Returns jobs added."""
    added = 0
    added += enqueue(
        db,
        school_id=school_id,
        kind="send_email",
        payload={"user_id": guardian_id, "subject": email_subject, "body": email_body},
        dedupe_key=f"{dedupe_prefix}:{guardian_id}:email",
    )
    added += enqueue(
        db,
        school_id=school_id,
        kind="send_sms",
        payload={"user_id": guardian_id, "text": sms_text},
        dedupe_key=f"{dedupe_prefix}:{guardian_id}:sms",
    )
    return added


@job_handler("send_email")
def handle_send_email(payload: dict[str, Any]) -> None:
    with SystemSessionLocal() as db:
        user = db.get(User, payload["user_id"])
    if not user or not user.email or user.email.lower().endswith(PLACEHOLDER_EMAIL_DOMAIN):
        return  # nothing to deliver to — done, not an error
    try:
        send_email(user.email, payload["subject"], payload["body"])
    except NotificationConfigError:
        return  # email isn't set up on this deployment; retrying can't help


@job_handler("send_sms")
def handle_send_sms(payload: dict[str, Any]) -> None:
    with SystemSessionLocal() as db:
        user = db.get(User, payload["user_id"])
    if not user or not user.phone:
        return
    try:
        send_sms(user.phone, payload["text"])
    except NotificationConfigError:
        return


@job_handler("notify_payment_result")
def handle_notify_payment_result(payload: dict[str, Any]) -> None:
    """Compose the parent-facing message for a payment outcome and fan it out
    to each approved guardian. Runs after the payment transaction committed."""
    payment_id, succeeded = payload["payment_id"], bool(payload["succeeded"])
    with SystemSessionLocal() as db:
        payment = db.get(Payment, payment_id)
        if not payment:
            return
        student = db.get(Student, payment.student_id)
        school = db.get(School, payment.school_id)
        if not student or not school:
            return

        guardian_ids = db.execute(
            select(StudentGuardian.user_id).where(
                StudentGuardian.student_id == student.id,
                StudentGuardian.status == GuardianLinkStatus.APPROVED,
            )
        ).scalars().all()
        if not guardian_ids:
            return

        if succeeded:
            remaining = Decimal("0")
            if payment.invoice_id:
                invoice = db.get(Invoice, payment.invoice_id)
                if invoice:
                    remaining = invoice.total_amount - invoice.amount_paid
            subject, body, sms_text = compose_payment_confirmation(
                student_name=student.full_name,
                school_name=school.name,
                amount=payment.amount,
                currency=school.currency,
                method=payment.method.value,
                remaining_balance=remaining,
            )
        else:
            subject, body, sms_text = compose_payment_failed(
                student_name=student.full_name,
                school_name=school.name,
                amount=payment.amount,
                currency=school.currency,
            )

        for gid in guardian_ids:
            enqueue_guardian_message(
                db,
                school_id=school.id,
                guardian_id=gid,
                email_subject=subject,
                email_body=body,
                sms_text=sms_text,
                dedupe_prefix=f"pay:{payment_id}:{'ok' if succeeded else 'fail'}",
            )
        db.commit()

"""
Fee reminder delivery — email via SMTP (any provider, incl. Gmail with an
app password), SMS via Africa's Talking.

Both are independently optional: if only email is configured, reminders
still work over email alone, and vice versa. A guardian with no phone on
file simply doesn't get an SMS attempt; one with no email doesn't get an
email attempt — neither is treated as an error.
"""

import smtplib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.core.config import settings

AT_SANDBOX_URL = "https://api.sandbox.africastalking.com/version1/messaging"
AT_LIVE_URL = "https://api.africastalking.com/version1/messaging"


class NotificationConfigError(Exception):
    """Raised when a channel is used without being configured — lets
    callers give a clear message instead of a confusing downstream failure."""


def compose_reminder(
    student_name: str,
    school_name: str,
    balance: Decimal,
    currency: str,
    due_date: datetime,
) -> tuple[str, str, str]:
    """Returns (email_subject, email_body, sms_text) for a fee reminder."""
    due_str = due_date.strftime("%d %B %Y")
    amount_str = f"{currency} {balance:,.2f}"

    subject = f"Fee reminder: {student_name} — {amount_str} due {due_str}"
    body = (
        f"Dear Parent/Guardian,\n\n"
        f"This is a reminder that {student_name}'s school fees balance of {amount_str} "
        f"is due on {due_str} at {school_name}.\n\n"
        f"You can pay via M-Pesa directly from your Ledgr parent portal, or contact "
        f"the school office if you have any questions.\n\n"
        f"Thank you,\n{school_name}"
    )
    sms_text = (
        f"{school_name}: {student_name}'s fee balance of {amount_str} is due {due_str}. "
        f"Pay via M-Pesa on your Ledgr portal. Thank you."
    )
    return subject, body, sms_text


def send_email(to_email: str, subject: str, body: str) -> None:
    if not (settings.smtp_host and settings.smtp_username and settings.smtp_password and settings.smtp_from_email):
        raise NotificationConfigError("Email is not configured (missing SMTP settings)")

    msg = MIMEMultipart()
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)


def send_sms(phone_number: str, message: str) -> dict:
    if not (settings.africastalking_username and settings.africastalking_api_key):
        raise NotificationConfigError("SMS is not configured (missing Africa's Talking credentials)")

    url = AT_SANDBOX_URL if settings.africastalking_sandbox else AT_LIVE_URL

    resp = httpx.post(
        url,
        headers={"apiKey": settings.africastalking_api_key, "Accept": "application/json"},
        data={
            "username": settings.africastalking_username,
            "to": phone_number,
            "message": message,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


@dataclass
class ReminderResult:
    guardian_email: str | None
    guardian_phone: str | None
    email_sent: bool
    sms_sent: bool
    errors: list[str]


def send_message_to_guardian(
    guardian_email: str | None,
    guardian_phone: str | None,
    email_subject: str,
    email_body: str,
    sms_text: str,
) -> ReminderResult:
    """Same delivery mechanics as send_reminder_to_guardian, but takes
    already-composed content instead of building a fee-specific message —
    what the bulk announcement feature uses to send an arbitrary school
    notice instead of a payment reminder."""
    email_sent = False
    sms_sent = False
    errors: list[str] = []

    if guardian_email:
        try:
            send_email(guardian_email, email_subject, email_body)
            email_sent = True
        except NotificationConfigError:
            pass
        except Exception as exc:  # noqa: BLE001 — one guardian's failed send shouldn't crash the batch
            errors.append(f"Email to {guardian_email} failed: {exc}")

    if guardian_phone:
        try:
            send_sms(guardian_phone, sms_text)
            sms_sent = True
        except NotificationConfigError:
            pass
        except Exception as exc:  # noqa: BLE001
            errors.append(f"SMS to {guardian_phone} failed: {exc}")

    return ReminderResult(
        guardian_email=guardian_email,
        guardian_phone=guardian_phone,
        email_sent=email_sent,
        sms_sent=sms_sent,
        errors=errors,
    )


def send_reminder_to_guardian(
    guardian_email: str | None,
    guardian_phone: str | None,
    student_name: str,
    school_name: str,
    balance: Decimal,
    currency: str,
    due_date: datetime,
) -> ReminderResult:
    subject, body, sms_text = compose_reminder(student_name, school_name, balance, currency, due_date)

    email_sent = False
    sms_sent = False
    errors: list[str] = []

    if guardian_email:
        try:
            send_email(guardian_email, subject, body)
            email_sent = True
        except NotificationConfigError:
            pass  # not configured — not an error, just skip this channel
        except Exception as exc:  # noqa: BLE001 — one guardian's failed send shouldn't crash the batch
            errors.append(f"Email to {guardian_email} failed: {exc}")

    if guardian_phone:
        try:
            send_sms(guardian_phone, sms_text)
            sms_sent = True
        except NotificationConfigError:
            pass
        except Exception as exc:  # noqa: BLE001
            errors.append(f"SMS to {guardian_phone} failed: {exc}")

    return ReminderResult(
        guardian_email=guardian_email,
        guardian_phone=guardian_phone,
        email_sent=email_sent,
        sms_sent=sms_sent,
        errors=errors,
    )

"""
Fee reminder delivery — email over HTTPS (Brevo or Resend) or SMTP, SMS via
Africa's Talking.

Why HTTPS first: hosts such as Render's free tier block outbound SMTP ports
(25/465/587), so `smtplib` simply times out there. A provider's HTTP API goes out
on port 443, which is never blocked. SMTP stays available for hosts that allow it.

Both channels are independently optional: if only email is configured, reminders
still work over email alone, and vice versa. A guardian with no phone on
file simply doesn't get an SMS attempt; one with no email doesn't get an
email attempt — neither is treated as an error.
"""

import logging
import smtplib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"
RESEND_URL = "https://api.resend.com/emails"
# Tests swap this for an httpx.MockTransport; production leaves it None.
_transport: httpx.BaseTransport | None = None

AT_SANDBOX_URL = "https://api.sandbox.africastalking.com/version1/messaging"
AT_LIVE_URL = "https://api.africastalking.com/version1/messaging"


class NotificationConfigError(Exception):
    """Raised when a channel is used without being configured — lets
    callers give a clear message instead of a confusing downstream failure."""


class EmailDeliveryError(Exception):
    """The email provider was reached but refused the message (bad key, unverified
    sender, invalid recipient...). The provider's own explanation is in the message."""


ESCALATION_LABELS = {1: "Reminder", 2: "Second reminder", 3: "Final notice"}


def compose_overdue_escalation(
    tier: int,
    student_name: str,
    school_name: str,
    balance: Decimal,
    currency: str,
    due_date: datetime,
) -> tuple[str, str, str]:
    """Returns (email_subject, email_body, sms_text) for an automated
    overdue escalation. Wording gets firmer at each tier — tier 1 reads as
    a routine reminder, tier 3 as a final notice — without ever threatening
    a specific consequence the school hasn't actually decided on."""
    due_str = due_date.strftime("%d %B %Y")
    amount_str = f"{currency} {balance:,.2f}"
    label = ESCALATION_LABELS.get(tier, "Reminder")

    if tier <= 1:
        opening = (
            f"This is a reminder that {student_name}'s school fees balance of {amount_str} "
            f"was due on {due_str} and remains unpaid."
        )
    elif tier == 2:
        opening = (
            f"This is a follow-up: {student_name}'s school fees balance of {amount_str} "
            f"has now been overdue since {due_str}."
        )
    else:
        opening = (
            f"This is a final notice: {student_name}'s school fees balance of {amount_str} "
            f"has been overdue since {due_str} and needs urgent attention."
        )

    subject = f"{label}: {student_name} — {amount_str} overdue since {due_str}"
    body = (
        f"Dear Parent/Guardian,\n\n{opening}\n\n"
        f"You can pay via M-Pesa directly from your Ledgr parent portal, or contact "
        f"the school office if you have any questions.\n\nThank you,\n{school_name}"
    )
    sms_text = f"{school_name}: {label} — {student_name}'s fee balance of {amount_str} overdue since {due_str}. Pay via M-Pesa on your Ledgr portal."
    return subject, body, sms_text


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


def compose_payment_confirmation(
    student_name: str,
    school_name: str,
    amount: Decimal,
    currency: str,
    method: str,
    remaining_balance: Decimal,
) -> tuple[str, str, str]:
    """Returns (email_subject, email_body, sms_text) confirming a payment
    just went through — sent right after M-Pesa (or any other method)
    confirms, so a parent doesn't have to keep checking the portal to know
    whether it worked."""
    amount_str = f"{currency} {amount:,.2f}"
    method_label = method.replace("_", " ").title()

    subject = f"Payment received: {student_name} — {amount_str}"
    if remaining_balance > 0:
        balance_line = f"The remaining balance on this invoice is {currency} {remaining_balance:,.2f}."
    else:
        balance_line = "This invoice is now fully paid."

    body = (
        f"Dear Parent/Guardian,\n\n"
        f"We've received a {method_label} payment of {amount_str} for {student_name} at {school_name}. "
        f"{balance_line}\n\n"
        f"A receipt is available in your Ledgr parent portal.\n\n"
        f"Thank you,\n{school_name}"
    )
    sms_text = f"{school_name}: Received {amount_str} for {student_name} via {method_label}. {balance_line}"
    return subject, body, sms_text


def compose_payment_failed(student_name: str, school_name: str, amount: Decimal, currency: str) -> tuple[str, str, str]:
    """Returns (email_subject, email_body, sms_text) for a payment attempt
    that did not go through (e.g. an M-Pesa STK push the parent cancelled,
    entered the wrong PIN for, or that timed out) — so they know to retry
    rather than assuming it went through silently."""
    amount_str = f"{currency} {amount:,.2f}"

    subject = f"Payment did not go through: {student_name} — {amount_str}"
    body = (
        f"Dear Parent/Guardian,\n\n"
        f"Your attempted payment of {amount_str} for {student_name} at {school_name} did not go through. "
        f"This can happen if the M-Pesa prompt was cancelled, timed out, or the PIN entered was incorrect.\n\n"
        f"No money has left your account. You can try again anytime from your Ledgr parent portal.\n\n"
        f"Thank you,\n{school_name}"
    )
    sms_text = f"{school_name}: Your payment of {amount_str} for {student_name} did not go through. No money was deducted. Please try again on your Ledgr portal."
    return subject, body, sms_text


def _smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_username and settings.smtp_password and _from_email())


def _from_email() -> str | None:
    return settings.email_from_email or settings.smtp_from_email


def _from_name() -> str:
    return settings.email_from_name or settings.smtp_from_name or "Ledgr"


def active_email_provider() -> str | None:
    """Which channel send_email will use, or None when email isn't set up."""
    if not _from_email():
        return None
    pref = (settings.email_provider or "auto").strip().lower()
    available = {
        "brevo": bool(settings.brevo_api_key),
        "resend": bool(settings.resend_api_key),
        "smtp": _smtp_configured(),
    }
    if pref in available:
        return pref if available[pref] else None
    for name in ("brevo", "resend", "smtp"):  # "auto"
        if available[name]:
            return name
    return None


def _explain_http_error(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        detail = data.get("message") or data.get("error") or data.get("name") or data
    except ValueError:
        detail = resp.text
    return f"{resp.status_code}: {str(detail)[:300]}"


def _send_via_brevo(to_email: str, subject: str, body: str) -> None:
    with httpx.Client(transport=_transport, timeout=15) as client:
        resp = client.post(
            BREVO_URL,
            headers={"api-key": settings.brevo_api_key or "", "accept": "application/json"},
            json={
                "sender": {"name": _from_name(), "email": _from_email()},
                "to": [{"email": to_email}],
                "subject": subject,
                "textContent": body,
            },
        )
    if resp.status_code >= 400:
        raise EmailDeliveryError(f"Brevo refused the email ({_explain_http_error(resp)})")


def _send_via_resend(to_email: str, subject: str, body: str) -> None:
    with httpx.Client(transport=_transport, timeout=15) as client:
        resp = client.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": f"{_from_name()} <{_from_email()}>",
                "to": [to_email],
                "subject": subject,
                "text": body,
            },
        )
    if resp.status_code >= 400:
        raise EmailDeliveryError(f"Resend refused the email ({_explain_http_error(resp)})")


def _send_via_smtp(to_email: str, subject: str, body: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = f"{_from_name()} <{_from_email()}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    if settings.smtp_port == 465:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
    with server:
        if settings.smtp_port != 465:
            server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)


def send_email(to_email: str, subject: str, body: str) -> None:
    provider = active_email_provider()
    if provider is None:
        raise NotificationConfigError(
            "Email is not configured (set BREVO_API_KEY or RESEND_API_KEY plus EMAIL_FROM_EMAIL, "
            "or the SMTP_* settings)"
        )
    if provider == "brevo":
        _send_via_brevo(to_email, subject, body)
    elif provider == "resend":
        _send_via_resend(to_email, subject, body)
    else:
        _send_via_smtp(to_email, subject, body)


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

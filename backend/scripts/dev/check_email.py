"""Check that email actually goes out BEFORE (or after) deploying.

    cd backend
    python -m scripts.dev.check_email you@example.com

Reads the email settings from backend/.env (or the environment, so you can also run it in a
Render shell), says which channel it will use, and sends one real test message through the same
code the app uses. Prints what to change if something is off. Never prints a key or password.
"""

import socket
import sys

from app.core.config import settings
from app.services import notification_service as ns

if len(sys.argv) != 2 or "@" not in sys.argv[1]:
    raise SystemExit("Usage: python -m scripts.dev.check_email you@example.com")
to = sys.argv[1]

provider = ns.active_email_provider()
print(f"EMAIL_PROVIDER={settings.email_provider}   -> using: {provider or 'NOTHING (email is not configured)'}")
print(f"From: {ns._from_name()} <{ns._from_email()}>")

if provider is None:
    raise SystemExit(
        "\nEmail is not configured. Set EMAIL_FROM_EMAIL plus ONE of:\n"
        "  BREVO_API_KEY   (free: 300 emails/day, brevo.com -> SMTP & API -> API keys)\n"
        "  RESEND_API_KEY  (free: 100 emails/day, resend.com -> API keys)\n"
        "Render's free tier blocks SMTP ports, so use one of the API keys there."
    )

if provider == "smtp":
    print(f"\nTesting a raw connection to {settings.smtp_host}:{settings.smtp_port} first...")
    try:
        socket.create_connection((settings.smtp_host, settings.smtp_port), timeout=8).close()
        print("  connected.")
    except OSError as exc:
        raise SystemExit(
            f"  FAILED: {exc}\n"
            "  Usually this means the host blocks outbound SMTP (Render's free tier blocks ports 25/465/587).\n"
            "  Switch to BREVO_API_KEY or RESEND_API_KEY — those use HTTPS and are never blocked."
        )

print(f"\nSending a test email to {to} ...")
try:
    ns.send_email(to, "Ledgr email check", "If you can read this, Ledgr can send email from this deployment.")
except ns.EmailDeliveryError as exc:
    raise SystemExit(
        f"\nThe provider refused it: {exc}\n"
        "Common causes: wrong API key, or the From address isn't a verified sender "
        "(Brevo: Senders, domains & dedicated IPs -> Senders; Resend: Domains)."
    )
except Exception as exc:  # noqa: BLE001
    raise SystemExit(f"\nCould not send: {type(exc).__name__}: {exc}")
print("Sent. Check the inbox (and spam) of", to)

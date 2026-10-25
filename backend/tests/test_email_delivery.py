"""Email goes out over HTTPS (Brevo / Resend) so it works on hosts that block SMTP ports."""

import json

import httpx
import pytest

from app.core.config import settings
from app.services import notification_service as ns


@pytest.fixture(autouse=True)
def clean_email_settings(monkeypatch):
    for name in ("brevo_api_key", "resend_api_key", "smtp_host", "smtp_username", "smtp_password", "smtp_from_email"):
        monkeypatch.setattr(settings, name, None)
    monkeypatch.setattr(settings, "email_from_email", "office@school.example")
    monkeypatch.setattr(settings, "email_from_name", "Greenfield Academy")
    monkeypatch.setattr(settings, "email_provider", "auto")
    yield
    monkeypatch.setattr(ns, "_transport", None)


def _mock(monkeypatch, status=201, body=None):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=body or {})

    monkeypatch.setattr(ns, "_transport", httpx.MockTransport(handler))
    return seen


def test_nothing_configured_raises_config_error():
    assert ns.active_email_provider() is None
    with pytest.raises(ns.NotificationConfigError):
        ns.send_email("a@b.example", "s", "b")


def test_a_from_address_is_required_even_with_a_key(monkeypatch):
    monkeypatch.setattr(settings, "brevo_api_key", "k")
    monkeypatch.setattr(settings, "email_from_email", None)
    assert ns.active_email_provider() is None


def test_auto_prefers_brevo_then_resend_then_smtp(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "r")
    assert ns.active_email_provider() == "resend"
    monkeypatch.setattr(settings, "brevo_api_key", "b")
    assert ns.active_email_provider() == "brevo"
    monkeypatch.setattr(settings, "brevo_api_key", None)
    monkeypatch.setattr(settings, "resend_api_key", None)
    for name, value in (("smtp_host", "smtp.example"), ("smtp_username", "u"), ("smtp_password", "p")):
        monkeypatch.setattr(settings, name, value)
    assert ns.active_email_provider() == "smtp"


def test_forcing_a_provider_that_is_not_configured_means_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "r")
    monkeypatch.setattr(settings, "email_provider", "brevo")
    assert ns.active_email_provider() is None


def test_brevo_request_shape(monkeypatch):
    monkeypatch.setattr(settings, "brevo_api_key", "brevo-key")
    seen = _mock(monkeypatch)
    ns.send_email("parent@example.com", "Reset your Ledgr password", "hello")
    req = seen[0]
    assert str(req.url) == ns.BREVO_URL
    assert req.headers["api-key"] == "brevo-key"
    body = json.loads(req.content)
    assert body == {
        "sender": {"name": "Greenfield Academy", "email": "office@school.example"},
        "to": [{"email": "parent@example.com"}],
        "subject": "Reset your Ledgr password",
        "textContent": "hello",
    }


def test_resend_request_shape(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "resend-key")
    seen = _mock(monkeypatch, status=200)
    ns.send_email("parent@example.com", "Subject", "hello")
    req = seen[0]
    assert str(req.url) == ns.RESEND_URL
    assert req.headers["authorization"] == "Bearer resend-key"
    assert json.loads(req.content) == {
        "from": "Greenfield Academy <office@school.example>",
        "to": ["parent@example.com"],
        "subject": "Subject",
        "text": "hello",
    }


def test_provider_refusal_surfaces_the_providers_reason(monkeypatch):
    monkeypatch.setattr(settings, "brevo_api_key", "bad")
    _mock(monkeypatch, status=401, body={"message": "Key not found", "code": "unauthorized"})
    with pytest.raises(ns.EmailDeliveryError) as e:
        ns.send_email("a@b.example", "s", "b")
    assert "401" in str(e.value) and "Key not found" in str(e.value)


def test_smtp_fallback_uses_implicit_tls_on_465(monkeypatch):
    for name, value in (("smtp_host", "smtp.example"), ("smtp_username", "u"), ("smtp_password", "p"), ("smtp_port", 465)):
        monkeypatch.setattr(settings, name, value)
    calls = []

    class FakeSMTP:
        def __init__(self, kind):
            self.kind = kind

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            calls.append("starttls")

        def login(self, u, p):
            calls.append(("login", u))

        def send_message(self, msg):
            calls.append(("send", msg["To"]))

    monkeypatch.setattr(ns.smtplib, "SMTP_SSL", lambda *a, **k: calls.append("ssl") or FakeSMTP("ssl"))
    monkeypatch.setattr(ns.smtplib, "SMTP", lambda *a, **k: calls.append("plain") or FakeSMTP("plain"))
    ns.send_email("to@example.com", "s", "b")
    assert calls == ["ssl", ("login", "u"), ("send", "to@example.com")]  # no STARTTLS on an SSL socket

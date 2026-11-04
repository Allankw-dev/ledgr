"""A tripwire for accidental exposure. It pins:

  * every route that needs NO login, and
  * every route open to ANY logged-in role (so each one is a conscious decision, usually with its own
    per-handler checks: approved-guardian links, class membership, "my own records only"),

and checks the sensitive routes are rate-limited and that CORS / config safeguards behave. Adding a new route
that is public or role-agnostic fails the first two tests until someone reviews it and adds it here on purpose.
"""

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.main import app
from tests.conftest import needs_db

# --- reviewed: each of these is intentionally reachable without logging in --------------------------
PUBLIC = {
    "GET /",
    "GET /health", "GET /health/ready", "GET /health/status",  # status needs MONITOR_TOKEN
    "GET /api/attachments/download",  # needs a signed, expiring link
    "GET /api/auth/setup-status",
    "POST /api/auth/login", "POST /api/auth/logout", "POST /api/auth/refresh", "POST /api/auth/google",
    "POST /api/auth/register-parent", "POST /api/auth/register-school",
    "POST /api/auth/forgot-password", "POST /api/auth/reset-password", "POST /api/auth/email-change/confirm",
    "POST /api/auth/2fa/verify-login", "POST /api/auth/webauthn/login/options", "POST /api/auth/webauthn/login/verify",
    "POST /api/payments/mpesa/callback", "POST /api/payments/c2b/validation", "POST /api/payments/c2b/confirmation",  # secret token
}

# --- reviewed: open to any signed-in role, each scoped inside the handler -------------------------
ANY_ROLE = {
    # your own account and credentials
    "GET /api/users/me", "PATCH /api/users/me", "GET /api/auth/2fa/status", "GET /api/auth/webauthn/credentials",
    "DELETE /api/auth/webauthn/credentials/{credential_id}", "POST /api/auth/webauthn/register/options", "POST /api/auth/webauthn/register/verify",
    "GET /api/notifications/mentions", "POST /api/notifications/mentions/seen", "GET /api/notifications/summary",
    # school-wide reference data that parents legitimately see
    "GET /api/classes", "GET /api/terms", "GET /api/fee-structures",
    # messaging: membership of the class / conversation is checked in the handler
    "GET /api/class-groups", "GET /api/class-groups/{class_id}/members", "GET /api/class-groups/{class_id}/messages",
    "GET /api/class-groups/{class_id}/messages/{message_id}/attachment-url", "GET /api/class-groups/{class_id}/messages/{message_id}/receipts",
    "POST /api/class-groups/{class_id}/messages", "POST /api/class-groups/{class_id}/messages/upload",
    "GET /api/direct/blocks", "POST /api/direct/blocks", "DELETE /api/direct/blocks/{blocked_user_id}", "GET /api/direct/contacts",
    "GET /api/direct/conversations", "POST /api/direct/conversations",
    "GET /api/direct/conversations/{conversation_id}/messages", "POST /api/direct/conversations/{conversation_id}/messages",
    "POST /api/direct/conversations/{conversation_id}/messages/upload", "POST /api/direct/conversations/{conversation_id}/report",
    "DELETE /api/direct/conversations/{conversation_id}/messages/{message_id}",
    "GET /api/direct/conversations/{conversation_id}/messages/{message_id}/attachment",
    # parent portal: scoped to the caller's own approved children
    "GET /api/parent/students", "GET /api/parent/notifications", "GET /api/parent/messages", "POST /api/parent/messages",
    "GET /api/parent/messages/typing", "POST /api/parent/messages/typing", "POST /api/parent/assistant/query",
    "GET /api/students/lookup", "POST /api/students/{student_id}/request-link",
    # money documents: approved guardian of that student, or school staff, nobody else
    "GET /api/students/{student_id}/statement", "GET /api/invoices/{invoice_id}/pdf", "GET /api/payments/{payment_id}/receipt",
    "GET /api/invoices/{invoice_id}/payment-plan/active", "POST /api/invoices/{invoice_id}/payment-plan/accept",
    "POST /api/invoices/{invoice_id}/payment-plan/cancel",
    "POST /api/payments/mpesa/stk-push",  # linked parent for their child, or admin/bursar
    "GET /api/payments/mpesa/status",  # one boolean about the caller's OWN school: is online M-Pesa switched on?
}


def _routes():
    for r in app.routes:
        if isinstance(r, APIRoute):
            yield r, ""
        elif type(r).__name__ == "_IncludedRouter":
            prefix = getattr(r.include_context, "prefix", "") or ""
            for rr in r.original_router.routes:
                if isinstance(rr, APIRoute):
                    yield rr, prefix


def _dep_names(dep, out):
    for d in dep.dependencies:
        out.add(getattr(d.call, "__name__", ""))
        _dep_names(d, out)


def _classify():
    public, any_role, endpoints = set(), set(), {}
    for r, prefix in _routes():
        names: set[str] = set()
        _dep_names(r.dependant, names)
        for method in r.methods - {"HEAD", "OPTIONS"}:
            key = f"{method} {prefix}{r.path}"
            endpoints[key] = f"{r.endpoint.__module__}.{r.endpoint.__name__}"
            if "checker" not in names and not ({"get_current_user", "get_school_scope"} & names):
                public.add(key)
            elif "checker" not in names:
                any_role.add(key)
    return public, any_role, endpoints


def test_the_set_of_public_routes_is_exactly_the_reviewed_list():
    public, _, _ = _classify()
    assert public - PUBLIC == set(), f"NEW public route(s), review before allowing: {sorted(public - PUBLIC)}"
    assert PUBLIC - public == set(), f"listed as public but now protected or removed (update the list): {sorted(PUBLIC - public)}"


def test_the_set_of_any_role_routes_is_exactly_the_reviewed_list():
    _, any_role, _ = _classify()
    assert any_role - ANY_ROLE == set(), (
        f"NEW route(s) open to every signed-in role (parents included). Add require_roles(...) or, if it is "
        f"scoped inside the handler, review it and list it here: {sorted(any_role - ANY_ROLE)}"
    )
    assert ANY_ROLE - any_role == set(), f"update the list: {sorted(ANY_ROLE - any_role)}"


SENSITIVE_MUST_BE_LIMITED = [
    "POST /api/payments/mpesa/stk-push", "POST /api/invoices/{invoice_id}/send-reminder",
    "POST /api/auth/2fa/setup", "POST /api/auth/2fa/enable", "POST /api/auth/2fa/disable",
    "DELETE /api/auth/webauthn/credentials/{credential_id}", "PATCH /api/users/me",
    "POST /api/platform/schools", "PATCH /api/platform/schools/{school_id}/subscription",
    "PUT /api/platform/schools/{school_id}/mpesa", "DELETE /api/platform/schools/{school_id}/mpesa",
    "POST /api/platform/schools/{school_id}/mpesa/test", "POST /api/platform/schools/{school_id}/mpesa/register-urls",
    "POST /api/platform/schools/{school_id}/mpesa/mode",
    "POST /api/auth/login", "POST /api/auth/register-parent", "POST /api/auth/forgot-password", "POST /api/auth/reset-password",
    "POST /api/students", "POST /api/invoices/{invoice_id}/void",
]


def test_the_sensitive_routes_are_rate_limited():
    _, _, endpoints = _classify()
    limited = set(limiter._route_limits.keys())
    missing = [k for k in SENSITIVE_MUST_BE_LIMITED if endpoints.get(k) not in limited]
    assert missing == [], f"no rate limit on: {missing}"


@needs_db
def test_the_mpesa_prompt_endpoint_really_stops_after_10_requests_a_minute(db, world):
    limiter.reset()
    client = TestClient(app)
    headers = {"Authorization": "Bearer " + create_access_token(world.bursar.id, world.school.id, "BURSAR")}
    body = {"invoice_id": world.invoice.id, "phone_number": "0712345678"}
    codes = [client.post("/api/payments/mpesa/stk-push", json=body, headers=headers).status_code for _ in range(12)]
    assert 429 not in codes[:10]
    assert codes[10:] == [429, 429]
    limiter.reset()


# ---- configuration safeguards ---------------------------------------------------------------------

BASE = dict(database_url="postgresql://u:p@db.example.com/x", jwt_secret="s" * 40)


def test_running_on_render_counts_as_production_even_if_environment_was_never_set(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    assert Settings(**BASE).is_production_like is False
    monkeypatch.setenv("RENDER", "true")
    assert Settings(**BASE).is_production_like is True


def test_a_wildcard_cors_origin_is_refused_everywhere_except_a_dev_machine(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    assert Settings(**BASE, cors_origins="*").cors_origin_list == ["*"]  # a developer's laptop
    with pytest.raises(ValueError):
        Settings(**BASE, cors_origins="*", environment="staging")
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(ValueError):
        Settings(**BASE, cors_origins="https://ok.example, *")


def test_cors_origins_are_cleaned_so_a_correct_looking_value_actually_matches(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    s = Settings(**BASE, cors_origins=" https://a.vercel.app/ ,https://b.example.com,, ")
    assert s.cors_origin_list == ["https://a.vercel.app", "https://b.example.com"]


@pytest.mark.parametrize("alg", ["none", "None", "RS256", "ES256", ""])
def test_only_hmac_token_algorithms_are_accepted_in_config(alg):
    with pytest.raises(ValueError):
        Settings(**BASE, jwt_algorithm=alg)


def test_cors_allows_the_frontend_and_refuses_everything_else():
    client = TestClient(app)
    origin = "http://localhost:5173"  # the test environment's CORS_ORIGINS default
    ok = client.options("/api/students", headers={"Origin": origin, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization,idempotency-key"})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == origin
    assert "access-control-allow-credentials" not in ok.headers  # no cookies are used, so none are honoured
    evil_origin = client.options("/api/students", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in evil_origin.headers
    odd_header = client.options("/api/students", headers={"Origin": origin, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "x-evil"})
    assert odd_header.status_code == 400
    odd_method = client.options("/api/students", headers={"Origin": origin, "Access-Control-Request-Method": "TRACE"})
    assert odd_method.status_code == 400


# ---- response headers -------------------------------------------------------------------------------


def test_json_responses_are_marked_no_store_but_a_routes_own_cache_policy_is_respected():
    client = TestClient(app)
    res = client.get("/health")
    assert res.headers["content-type"].startswith("application/json")
    assert res.headers["cache-control"] == "no-store"
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"


def test_the_public_get_routes_are_rate_limited_too():
    _, _, endpoints = _classify()
    limited = set(limiter._route_limits.keys())
    for key in ("GET /health/ready", "GET /api/auth/setup-status", "GET /api/attachments/download"):
        assert endpoints[key] in limited, key


# ---- request size and field limits --------------------------------------------------------------------


def test_an_oversized_json_body_is_refused_before_it_is_read():
    client = TestClient(app)
    huge = b'{"email": "a@b.com", "password": "' + b"x" * (1024 * 1024 + 10) + b'"}'
    res = client.post("/api/auth/login", content=huge, headers={"Content-Type": "application/json"})
    assert res.status_code == 413
    assert "too large" in res.json()["detail"].lower()


def test_an_oversized_body_with_no_declared_length_is_cut_off_as_it_streams():
    client = TestClient(app)

    def chunks():
        for _ in range(40):  # 40 x 64 KiB = 2.5 MiB, never announced up front
            yield b"x" * 65536

    res = client.post("/api/auth/login", content=chunks(), headers={"Content-Type": "application/json"})
    assert res.status_code == 413


def test_normal_requests_and_uploads_are_not_affected_by_the_limit():
    client = TestClient(app)
    ok = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "whatever-it-is"})
    assert ok.status_code == 401  # reached the app and was judged on its merits
    from app.core.body_limit import _limit_for
    from app.core.config import settings

    assert _limit_for("/api/class-groups/abc/messages/upload") > settings.max_upload_mb * 1024 * 1024
    assert _limit_for("/api/students") == 1024 * 1024


@pytest.mark.parametrize(
    "model, field",
    [("student.CreateStudentRequest", "full_name"), ("student.CreateStudentRequest", "admission_number"), ("teacher.CreateTeacherRequest", "full_name"),
     ("auth.RegisterSchoolRequest", "school_name"), ("term.CreateClassRequest", "name"), ("payment.ReversePaymentRequest", "reason"), ("mpesa.StkPushRequest", "phone_number")],
)
def test_free_text_request_fields_have_a_maximum_length(model, field):
    import importlib

    module, cls = model.split(".")
    info = getattr(importlib.import_module(f"app.schemas.{module}"), cls).model_fields[field]
    assert any(getattr(m, "max_length", None) for m in info.metadata), f"{model}.{field} has no max_length"


def test_every_free_text_request_field_in_the_schemas_is_bounded_except_the_deliberate_exceptions():
    """New request models can't quietly add an unbounded text field."""
    import importlib, pkgutil, typing

    import annotated_types
    from pydantic import BaseModel

    import app.schemas as pkg

    EXEMPT = {"PendingGuardianRequest", "C2BPayload"}  # a response model; the Safaricom webhook (never reject a real payment)
    offenders = []
    for mi in pkgutil.iter_modules(pkg.__path__):
        mod = importlib.import_module(f"app.schemas.{mi.name}")
        for name, cls in vars(mod).items():
            if not (isinstance(cls, type) and issubclass(cls, BaseModel) and cls.__module__ == mod.__name__):
                continue
            if name in EXEMPT or not name.endswith(("Request", "Create", "Update", "Body", "Input", "Payload", "Data")):
                continue
            for fname, f in cls.model_fields.items():
                ann = f.annotation
                args = [a for a in typing.get_args(ann) if a is not type(None)]
                plain_text = ann is str or (typing.get_origin(ann) in (typing.Union, __import__("types").UnionType) and args == [str])
                if plain_text and not any(isinstance(m, annotated_types.MaxLen) or getattr(m, "max_length", None) for m in f.metadata):
                    offenders.append(f"{mi.name}.{name}.{fname}")
    assert offenders == [], f"unbounded text fields: {offenders}"


def test_the_teacher_class_assignment_lists_are_bounded():
    from app.schemas.teacher import CreateTeacherRequest, UpdateTeacherClassesRequest

    for model in (CreateTeacherRequest, UpdateTeacherClassesRequest):
        assert any(getattr(m, "max_length", None) == 200 for m in model.model_fields["class_ids"].metadata), model.__name__


def test_a_configured_shortcode_on_the_sandbox_address_logs_a_loud_warning_outside_development(monkeypatch, caplog):
    """Unset MPESA_BASE_URL means Safaricom's SANDBOX: STK prompts reach no real phone. The old comment said to
    unset it for production, so the mistake is easy to make and silent without this warning."""
    import logging

    monkeypatch.delenv("RENDER", raising=False)
    with caplog.at_level(logging.WARNING, logger="ledgr.security"):
        Settings(**BASE, environment="staging", mpesa_shortcode="174379")
    assert "SANDBOX" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="ledgr.security"):
        Settings(**BASE, environment="staging", mpesa_shortcode="174379", mpesa_base_url="https://api.safaricom.co.ke")  # live: quiet
        Settings(**BASE, environment="staging")  # no M-Pesa configured: quiet
        Settings(**BASE, mpesa_shortcode="174379")  # a developer's machine: quiet
    assert "SANDBOX" not in caplog.text

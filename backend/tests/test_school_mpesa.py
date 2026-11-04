"""Each school can have its OWN M-Pesa paybill.

These tests use a fake Safaricom (httpx.MockTransport) so they can check what really goes out: which key and
secret are used, which shortcode is in the request, which callback address is given. The questions that matter:

  * can a school ever pay into another school's paybill?   (no: a school with no set-up is OFF, never "the default")
  * can one school's webhook address touch another school?  (no)
  * can a payment to school B's paybill be credited to school A's student?  (no, even with the same admission number)
  * do the secrets ever leave the server?                   (no: not in a response, a log line or the audit trail)
"""

import base64
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.message_crypto import DecryptionError
from app.core.rate_limit import limiter
from app.core.secret_crypto import decrypt_secret, encrypt_secret
from app.core.security import create_access_token
from app.main import app
from app.models.enums import InvoiceStatus, PaymentStatus, UserRole
from app.models.invoice import Invoice
from app.models.mpesa_account import SchoolMpesaAccount
from app.models.mpesa_transaction import MpesaTransaction
from app.models.payment import AuditLog, Payment
from app.models.school import School, User
from app.models.student import Student, Term
from app.services import mpesa_accounts as accounts
from app.services.mpesa_service import MpesaCredentials
from tests.conftest import needs_db, use_global_mpesa

pytestmark = needs_db

ORIGIN = "https://api.ledgr.test"
GLOBAL_CALLBACK = f"{ORIGIN}/api/payments/mpesa/callback?token=global-secret-token-123456789"

# Distinctive, so a leak is unmistakable when we search responses, logs and rows for them.
A_KEY, A_SECRET, A_PASSKEY = "KEY-of-school-A-aaaa1111", "SECRET-of-school-A-aaaa2222", "PASSKEY-of-school-A-aaaa3333"
B_KEY, B_SECRET, B_PASSKEY = "KEY-of-school-B-bbbb1111", "SECRET-of-school-B-bbbb2222", "PASSKEY-of-school-B-bbbb3333"
ALL_SECRETS = [A_KEY, A_SECRET, A_PASSKEY, B_KEY, B_SECRET, B_PASSKEY]


# ---- fake Safaricom -------------------------------------------------------------------------------


class Daraja:
    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.oauth_status = 200
        self.register_status = 200
        self.unreachable = False

    def _by(self, suffix):
        return [r for r in self.requests if r.url.path.endswith(suffix)]

    def oauth_logins(self) -> list[str]:
        """The "key:secret" each token request was made with."""
        return [base64.b64decode(r.headers["Authorization"].split(" ", 1)[1]).decode() for r in self._by("/oauth/v1/generate")]

    def stk_payloads(self) -> list[dict]:
        return [json.loads(r.content) for r in self._by("/stkpush/v1/processrequest")]

    def registrations(self) -> list[dict]:
        return [json.loads(r.content) for r in self._by("/c2b/v2/registerurl")]


@pytest.fixture()
def daraja(monkeypatch):
    d = Daraja()
    real_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        if d.unreachable:
            raise httpx.ConnectError("no route to Safaricom", request=request)
        d.requests.append(request)
        path = request.url.path
        if path.endswith("/oauth/v1/generate"):
            if d.oauth_status != 200:
                return httpx.Response(d.oauth_status, json={"errorMessage": "Bad credentials SAFARICOM-INTERNAL-DETAIL"})
            return httpx.Response(200, json={"access_token": "tok"})
        if path.endswith("/stkpush/v1/processrequest"):
            return httpx.Response(200, json={"CheckoutRequestID": f"ws_CO_{uuid.uuid4().hex[:10]}", "MerchantRequestID": "m", "CustomerMessage": "ok"})
        if path.endswith("/c2b/v2/registerurl"):
            if d.register_status != 200:
                return httpx.Response(d.register_status, json={"errorMessage": "Invalid ShortCode SAFARICOM-INTERNAL-DETAIL"})
            return httpx.Response(200, json={"ResponseDescription": "Success"})
        return httpx.Response(404)

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: real_client(transport=httpx.MockTransport(handler)))
    return d


# ---- people and schools ---------------------------------------------------------------------------


def _token(user, role):
    return {"Authorization": "Bearer " + create_access_token(user.id, user.school_id, role)}


@pytest.fixture()
def http(db, world, monkeypatch):
    from app.core.config import settings

    limiter.reset()
    monkeypatch.setattr(settings, "mpesa_callback_url", GLOBAL_CALLBACK)  # tells the server its own public address
    monkeypatch.setattr(settings, "mpesa_callback_secret", "global-secret-token-123456789")
    yield TestClient(app)
    limiter.reset()


@pytest.fixture()
def operator(db):
    op = User(school_id=None, email=f"op-{uuid.uuid4().hex[:6]}@ledgr.test", password_hash="x", role=UserRole.SUPER_ADMIN, full_name="Operator", is_active=True)
    db.add(op)
    db.commit()
    return SimpleNamespace(user=op, headers={"Authorization": "Bearer " + create_access_token(op.id, None, "SUPER_ADMIN")})


def make_school(db, name, *, mode="OFF", admission="1001", total="5000.00"):
    """A school with a bursar, one student and one unpaid invoice. Admission numbers deliberately repeat across schools."""
    school = School(name=name, country="KE", contact_email=f"{uuid.uuid4().hex[:6]}@x.test", mpesa_mode=mode)
    db.add(school)
    db.flush()
    bursar = User(school_id=school.id, email=f"b-{uuid.uuid4().hex[:6]}@x.test", password_hash="x", role=UserRole.BURSAR, full_name="Bursar", is_active=True)
    student = Student(school_id=school.id, admission_number=admission, full_name=f"Kid of {name}")
    term = Term(school_id=school.id, name="Term 1", start_date=datetime.now(timezone.utc), end_date=datetime.now(timezone.utc) + timedelta(days=90))
    db.add_all([bursar, student, term])
    db.flush()
    invoice = Invoice(
        school_id=school.id, student_id=student.id, term_id=term.id, total_amount=Decimal(total),
        due_date=datetime.now(timezone.utc) + timedelta(days=30), status=InvoiceStatus.ISSUED,
    )
    db.add(invoice)
    db.commit()
    return SimpleNamespace(school=school, bursar=bursar, student=student, invoice=invoice, headers={"Authorization": "Bearer " + create_access_token(bursar.id, school.id, "BURSAR")})


def save_account(http, operator, school, *, shortcode, key, secret, passkey, environment="PRODUCTION"):
    res = http.put(
        f"/api/platform/schools/{school.id}/mpesa", headers=operator.headers,
        json={"environment": environment, "shortcode": shortcode, "consumer_key": key, "consumer_secret": secret, "passkey": passkey},
    )
    assert res.status_code == 200, res.text
    return res


def go_live(http, operator, school, daraja, **account):
    save_account(http, operator, school, **account)
    assert http.post(f"/api/platform/schools/{school.id}/mpesa/test", headers=operator.headers).json()["ok"] is True
    res = http.post(f"/api/platform/schools/{school.id}/mpesa/mode", headers=operator.headers, json={"mode": "OWN"})
    assert res.status_code == 200, res.text


@pytest.fixture()
def school_a(db, world, http, operator, daraja):
    """world's school, on its OWN live paybill 111111."""
    a = SimpleNamespace(school=world.school, bursar=world.bursar, student=world.student, invoice=world.invoice, headers=_token(world.bursar, "BURSAR"))
    go_live(http, operator, a.school, daraja, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)
    return a


@pytest.fixture()
def school_b(db, world, http, operator, daraja):
    """A second school, on ITS OWN live paybill 222222, with the SAME admission number as school A's student."""
    b = make_school(db, "Beta School", admission="1001")
    go_live(http, operator, b.school, daraja, shortcode="222222", key=B_KEY, secret=B_SECRET, passkey=B_PASSKEY)
    return b


def stk(http, who, amount="2000"):
    return http.post("/api/payments/mpesa/stk-push", headers=who.headers, json={"invoice_id": who.invoice.id, "phone_number": "0712345678", "amount": amount})


def account_row(db, school):
    db.expire_all()
    return db.execute(select(SchoolMpesaAccount).where(SchoolMpesaAccount.school_id == school.id)).scalar_one_or_none()


# ======================================================================================================
# Storage: the secrets are encrypted, bound to their school, and never come back out
# ======================================================================================================


def test_a_secret_decrypts_only_with_the_context_it_was_stored_under():
    token = encrypt_secret("hunter2-hunter2", "mpesa|school-1|passkey")
    assert decrypt_secret(token, "mpesa|school-1|passkey") == "hunter2-hunter2"
    for wrong in ("mpesa|school-2|passkey", "mpesa|school-1|consumer_key"):
        with pytest.raises(DecryptionError):
            decrypt_secret(token, wrong)
    with pytest.raises(DecryptionError):
        decrypt_secret(token[:-4] + "AAAA", "mpesa|school-1|passkey")  # tampered


def test_two_encryptions_of_the_same_secret_differ():
    assert encrypt_secret("same", "ctx") != encrypt_secret("same", "ctx")


def test_credentials_never_show_their_secrets_when_printed():
    creds = MpesaCredentials(shortcode="123456", base_url="https://x", consumer_key="K-LEAK", consumer_secret="S-LEAK", passkey="P-LEAK")
    text = repr(creds) + str(creds)
    assert "K-LEAK" not in text and "S-LEAK" not in text and "P-LEAK" not in text


def test_saved_secrets_are_stored_as_ciphertext_and_decrypt_back(db, world, http, operator, daraja):
    save_account(http, operator, world.school, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)
    row = account_row(db, world.school)
    for stored in (row.consumer_key_enc, row.consumer_secret_enc, row.passkey_enc):
        assert not any(secret in stored for secret in ALL_SECRETS)
    creds = accounts.credentials_from_account(row)
    assert (creds.consumer_key, creds.consumer_secret, creds.passkey, creds.shortcode) == (A_KEY, A_SECRET, A_PASSKEY, "111111")


def test_a_row_copied_to_another_school_cannot_be_decrypted_there(db, world, http, operator, daraja):
    save_account(http, operator, world.school, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)
    other = make_school(db, "Other School")
    row = account_row(db, world.school)
    stolen = SchoolMpesaAccount(
        school_id=other.school.id, environment="SANDBOX", shortcode="999999", consumer_key_enc=row.consumer_key_enc,
        consumer_secret_enc=row.consumer_secret_enc, passkey_enc=row.passkey_enc,
    )
    db.add(stolen)
    db.commit()
    with pytest.raises(DecryptionError):
        accounts.credentials_from_account(stolen)


def test_no_response_log_line_or_audit_entry_ever_contains_a_secret(db, world, http, operator, daraja, caplog):
    caplog.set_level(logging.DEBUG)
    responses = [save_account(http, operator, world.school, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)]
    base = f"/api/platform/schools/{world.school.id}/mpesa"
    responses.append(http.get(base, headers=operator.headers))
    responses.append(http.post(f"{base}/test", headers=operator.headers))
    responses.append(http.post(f"{base}/register-urls", headers=operator.headers))
    responses.append(http.post(f"{base}/mode", headers=operator.headers, json={"mode": "OWN"}))
    daraja.oauth_status = 401
    responses.append(http.post(f"{base}/test", headers=operator.headers))
    daraja.oauth_status, daraja.register_status = 200, 400
    responses.append(http.post(f"{base}/register-urls", headers=operator.headers))
    responses.append(http.delete(base, headers=operator.headers))
    audit = json.dumps([a.log_metadata for a in db.execute(select(AuditLog)).scalars()], default=str)
    everything = "\n".join(r.text for r in responses) + caplog.text + audit
    assert [s for s in ALL_SECRETS if s in everything] == []
    # Safaricom's raw reply stays in the server log for the operator; it is never relayed to the browser or filed away.
    assert "SAFARICOM-INTERNAL-DETAIL" not in "\n".join(r.text for r in responses) + audit


# ======================================================================================================
# The operator screen: who may use it, and what it does
# ======================================================================================================


def test_only_the_platform_operator_can_use_the_mpesa_setup_routes(db, world, http):
    base = f"/api/platform/schools/{world.school.id}/mpesa"
    calls = [("get", base, None), ("put", base, {"environment": "SANDBOX", "shortcode": "174379", "consumer_key": "k" * 10, "consumer_secret": "s" * 10, "passkey": "p" * 10}),
             ("delete", base, None), ("post", base + "/test", None), ("post", base + "/register-urls", None), ("post", base + "/mode", {"mode": "OWN"})]
    parent = User(school_id=world.school.id, email="par@x.test", password_hash="x", role=UserRole.PARENT, full_name="P", is_active=True)
    db.add(parent)
    db.commit()
    for who, role in ((world.bursar, "BURSAR"), (parent, "PARENT")):
        for method, url, body in calls:
            res = getattr(http, method)(url, headers=_token(who, role), **({"json": body} if body is not None else {}))
            assert res.status_code == 403, (role, method, url)
    for method, url, body in calls:
        assert getattr(http, method)(url, **({"json": body} if body is not None else {})).status_code in (401, 403)
    assert db.execute(select(SchoolMpesaAccount)).first() is None


def test_the_first_save_needs_all_three_secrets_and_a_valid_paybill(db, world, http, operator):
    url = f"/api/platform/schools/{world.school.id}/mpesa"
    res = http.put(url, headers=operator.headers, json={"environment": "SANDBOX", "shortcode": "174379", "consumer_key": "k" * 10})
    assert res.status_code == 422 and "consumer secret" in res.text and "passkey" in res.text
    bad = {"environment": "SANDBOX", "consumer_key": "k" * 10, "consumer_secret": "s" * 10, "passkey": "p" * 10}
    assert http.put(url, headers=operator.headers, json={**bad, "shortcode": "12ab"}).status_code == 422
    assert http.put(url, headers=operator.headers, json={**bad, "shortcode": "174379", "passkey": "has a space"}).status_code == 422
    assert http.put(url, headers=operator.headers, json={**bad, "shortcode": "174379", "environment": "LIVE"}).status_code == 422
    assert account_row(db, world.school) is None


def test_the_status_never_includes_the_secrets_only_whether_there_is_an_account(db, world, http, operator, daraja):
    save_account(http, operator, world.school, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)
    body = http.get(f"/api/platform/schools/{world.school.id}/mpesa", headers=operator.headers).json()
    assert body["has_account"] is True and body["shortcode"] == "111111" and body["environment"] == "PRODUCTION"
    assert body["mode"] == "OFF" and body["tested_at"] is None
    assert not {"consumer_key", "consumer_secret", "passkey", "consumer_key_enc"} & set(body)


def test_editing_without_new_secrets_keeps_the_saved_ones_but_asks_for_a_new_test(db, world, http, operator, daraja):
    go_live(http, operator, world.school, daraja, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)
    res = http.put(
        f"/api/platform/schools/{world.school.id}/mpesa", headers=operator.headers,
        json={"environment": "PRODUCTION", "shortcode": "111112", "consumer_key": "", "consumer_secret": None},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"]["shortcode"] == "111112" and body["status"]["tested_at"] is None
    assert body["status"]["mode"] == "OFF" and "OFF" in body["message"]  # live payments are never left on untested details
    creds = accounts.credentials_from_account(account_row(db, world.school))
    assert (creds.consumer_key, creds.consumer_secret, creds.passkey) == (A_KEY, A_SECRET, A_PASSKEY)


def test_replacing_one_secret_leaves_the_other_two_alone(db, world, http, operator, daraja):
    save_account(http, operator, world.school, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)
    http.put(f"/api/platform/schools/{world.school.id}/mpesa", headers=operator.headers, json={"environment": "PRODUCTION", "shortcode": "111111", "passkey": "NEW-PASSKEY-9999"})
    creds = accounts.credentials_from_account(account_row(db, world.school))
    assert (creds.consumer_key, creds.consumer_secret, creds.passkey) == (A_KEY, A_SECRET, "NEW-PASSKEY-9999")


def test_two_schools_cannot_both_own_the_same_live_paybill_but_sandbox_may_share(db, world, http, operator, daraja):
    other = make_school(db, "Other School")
    save_account(http, operator, world.school, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)
    res = http.put(
        f"/api/platform/schools/{other.school.id}/mpesa", headers=operator.headers,
        json={"environment": "PRODUCTION", "shortcode": "111111", "consumer_key": B_KEY, "consumer_secret": B_SECRET, "passkey": B_PASSKEY},
    )
    assert res.status_code == 409
    # Safaricom's public sandbox shortcode is shared by everyone testing, so sandbox accounts may repeat it.
    save_account(http, operator, world.school, shortcode="174379", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY, environment="SANDBOX")
    save_account(http, operator, other.school, shortcode="174379", key=B_KEY, secret=B_SECRET, passkey=B_PASSKEY, environment="SANDBOX")


def test_the_connection_test_uses_the_schools_own_key_and_secret(db, world, http, operator, daraja):
    save_account(http, operator, world.school, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)
    res = http.post(f"/api/platform/schools/{world.school.id}/mpesa/test", headers=operator.headers).json()
    assert res["ok"] is True and res["status"]["tested_at"] is not None
    assert daraja.oauth_logins() == [f"{A_KEY}:{A_SECRET}"]
    assert all("api.safaricom.co.ke" in str(r.url) for r in daraja.requests)  # PRODUCTION means the live address, not the sandbox


def test_a_sandbox_account_talks_to_the_sandbox(db, world, http, operator, daraja):
    save_account(http, operator, world.school, shortcode="174379", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY, environment="SANDBOX")
    http.post(f"/api/platform/schools/{world.school.id}/mpesa/test", headers=operator.headers)
    assert all("sandbox.safaricom.co.ke" in str(r.url) for r in daraja.requests)


def test_a_failed_connection_test_says_so_plainly_and_leaves_it_untested(db, world, http, operator, daraja):
    save_account(http, operator, world.school, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)
    daraja.oauth_status = 401
    res = http.post(f"/api/platform/schools/{world.school.id}/mpesa/test", headers=operator.headers).json()
    assert res["ok"] is False and "rejected" in res["message"] and res["status"]["tested_at"] is None
    assert res["status"]["last_error"] == res["message"]
    daraja.oauth_status, daraja.unreachable = 200, True
    res = http.post(f"/api/platform/schools/{world.school.id}/mpesa/test", headers=operator.headers).json()
    assert res["ok"] is False and "reach Safaricom" in res["message"]


def test_switching_to_the_schools_own_paybill_needs_saved_and_tested_details(db, world, http, operator, daraja):
    url = f"/api/platform/schools/{world.school.id}/mpesa/mode"
    assert http.post(url, headers=operator.headers, json={"mode": "OWN"}).status_code == 409  # nothing saved
    save_account(http, operator, world.school, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)
    assert http.post(url, headers=operator.headers, json={"mode": "OWN"}).status_code == 409  # saved but never tested
    http.post(f"/api/platform/schools/{world.school.id}/mpesa/test", headers=operator.headers)
    assert http.post(url, headers=operator.headers, json={"mode": "OWN"}).json()["status"]["mode"] == "OWN"
    assert http.post(url, headers=operator.headers, json={"mode": "OFF"}).json()["status"]["mode"] == "OFF"
    assert http.post(url, headers=operator.headers, json={"mode": "NOPE"}).status_code == 422


def test_the_server_wide_paybill_needs_complete_server_settings_and_warns_when_shared(db, world, http, operator, monkeypatch):
    other = make_school(db, "Other School")
    url = f"/api/platform/schools/{other.school.id}/mpesa/mode"
    assert http.post(url, headers=operator.headers, json={"mode": "GLOBAL"}).status_code == 409  # MPESA_* not set
    use_global_mpesa(db, world.school, monkeypatch)
    res = http.post(url, headers=operator.headers, json={"mode": "GLOBAL"}).json()
    assert res["status"]["mode"] == "GLOBAL" and "also use the server-wide paybill" in res["message"]


def test_registering_with_safaricom_gives_the_school_its_own_addresses(db, world, http, operator, daraja):
    save_account(http, operator, world.school, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)
    res = http.post(f"/api/platform/schools/{world.school.id}/mpesa/register-urls", headers=operator.headers).json()
    assert res["ok"] is True and res["status"]["c2b_registered_at"] is not None
    (reg,) = daraja.registrations()
    assert reg["ShortCode"] == "111111"
    token = reg["ConfirmationURL"].split("token=")[1]
    assert reg["ConfirmationURL"].startswith(f"{ORIGIN}/api/payments/c2b/confirmation?token=")
    assert reg["ValidationURL"].startswith(f"{ORIGIN}/api/payments/c2b/validation?token=")
    assert accounts.verify_school_webhook_token(token) == world.school.id
    assert "mpesa" not in reg["ConfirmationURL"].lower().replace("/api/payments", "")  # Daraja refuses the word "mpesa" in C2B addresses
    assert daraja.oauth_logins() == [f"{A_KEY}:{A_SECRET}"]


def test_registering_is_refused_without_a_public_https_address(db, world, http, operator, daraja, monkeypatch):
    from app.core.config import settings

    save_account(http, operator, world.school, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)
    url = f"/api/platform/schools/{world.school.id}/mpesa/register-urls"
    monkeypatch.setattr(settings, "mpesa_callback_url", "http://localhost:4000/api/payments/mpesa/callback")
    assert http.post(url, headers=operator.headers).status_code == 409  # Safaricom only calls https
    monkeypatch.setattr(settings, "mpesa_callback_url", None)
    assert http.post(url, headers=operator.headers).status_code == 409  # the server doesn't know its own address
    assert daraja.registrations() == []


def test_a_refused_registration_is_reported_without_safaricoms_reply(db, world, http, operator, daraja):
    save_account(http, operator, world.school, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)
    daraja.register_status = 400
    res = http.post(f"/api/platform/schools/{world.school.id}/mpesa/register-urls", headers=operator.headers).json()
    assert res["ok"] is False and "refused" in res["message"] and res["status"]["c2b_registered_at"] is None
    assert "SAFARICOM-INTERNAL-DETAIL" not in json.dumps(res)


def test_every_change_is_in_the_audit_trail_without_secrets(db, world, http, operator, daraja):
    go_live(http, operator, world.school, daraja, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)
    http.post(f"/api/platform/schools/{world.school.id}/mpesa/register-urls", headers=operator.headers)
    actions = [a.action for a in db.execute(select(AuditLog).where(AuditLog.school_id == world.school.id)).scalars()]
    for expected in ("SCHOOL_MPESA_SAVED", "SCHOOL_MPESA_TESTED", "SCHOOL_MPESA_MODE_CHANGED", "SCHOOL_MPESA_URLS_REGISTERED"):
        assert expected in actions
    saved = db.execute(select(AuditLog).where(AuditLog.action == "SCHOOL_MPESA_SAVED")).scalars().first()
    assert saved.user_id == operator.user.id and saved.log_metadata["secrets_replaced"] == ["consumer_key", "consumer_secret", "passkey"]


def test_removing_the_details_switches_the_school_off(db, world, http, operator, daraja):
    go_live(http, operator, world.school, daraja, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)
    res = http.delete(f"/api/platform/schools/{world.school.id}/mpesa", headers=operator.headers).json()
    assert res["status"]["mode"] == "OFF" and res["status"]["has_account"] is False
    assert account_row(db, world.school) is None


def test_a_school_added_by_the_operator_starts_with_mpesa_off(db, world, http, operator, monkeypatch):
    monkeypatch.setattr("app.routers.platform.send_email", lambda *a, **k: None)
    res = http.post("/api/platform/schools", headers=operator.headers, json={"school_name": "Brand New", "admin_full_name": "Ada Admin", "admin_email": "ada@brandnew.example"})
    assert res.status_code == 201
    assert db.get(School, res.json()["id"]).mpesa_mode == "OFF"


def test_the_very_first_school_on_a_fresh_deployment_uses_the_server_wide_paybill(db):
    limiter.reset()
    res = TestClient(app).post(
        "/api/auth/register-school",
        json={"school_name": "First School", "country": "KE", "currency": "KES", "admin_email": "first@school.example", "admin_password": "Tr0ub4dor&3 horse", "admin_full_name": "First Admin"},
    )
    assert res.status_code == 201, res.text
    assert db.execute(select(School.mpesa_mode)).scalar_one() == "GLOBAL"


# ======================================================================================================
# Starting a payment: which paybill is used
# ======================================================================================================


def test_a_school_with_nothing_set_up_cannot_start_an_mpesa_payment(db, world, http, daraja, monkeypatch):
    use_global_mpesa(db, make_school(db, "Some Other School").school, monkeypatch)  # the server HAS a paybill; this school isn't on it
    res = stk(http, SimpleNamespace(headers=_token(world.bursar, "BURSAR"), invoice=world.invoice))
    assert res.status_code == 409 and "aren't switched on" in res.json()["detail"]
    assert daraja.requests == []  # nothing was sent to Safaricom
    assert db.execute(select(Payment)).first() is None  # and no pending payment was left behind


def test_the_status_route_tells_the_frontend_whether_to_show_the_button(db, world, http, operator, daraja, monkeypatch):
    headers = _token(world.bursar, "BURSAR")
    assert http.get("/api/payments/mpesa/status", headers=headers).json() == {"enabled": False}  # new school: OFF
    go_live(http, operator, world.school, daraja, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)
    assert http.get("/api/payments/mpesa/status", headers=headers).json() == {"enabled": True}
    http.post(f"/api/platform/schools/{world.school.id}/mpesa/mode", headers=operator.headers, json={"mode": "OFF"})
    assert http.get("/api/payments/mpesa/status", headers=headers).json() == {"enabled": False}
    use_global_mpesa(db, world.school, monkeypatch)
    assert http.get("/api/payments/mpesa/status", headers=headers).json() == {"enabled": True}


def test_the_status_route_is_false_when_the_server_does_not_know_its_own_address(db, world, http, operator, daraja, monkeypatch):
    from app.core.config import settings

    go_live(http, operator, world.school, daraja, shortcode="111111", key=A_KEY, secret=A_SECRET, passkey=A_PASSKEY)
    monkeypatch.setattr(settings, "mpesa_callback_url", None)
    assert http.get("/api/payments/mpesa/status", headers=_token(world.bursar, "BURSAR")).json() == {"enabled": False}


def test_a_school_on_the_server_wide_paybill_uses_the_server_wide_credentials(db, world, http, daraja, monkeypatch):
    use_global_mpesa(db, world.school, monkeypatch, callback_url=GLOBAL_CALLBACK)
    res = stk(http, SimpleNamespace(headers=_token(world.bursar, "BURSAR"), invoice=world.invoice), amount="3000")
    assert res.status_code == 201, res.text
    assert daraja.oauth_logins() == ["global-key:global-secret"]
    (payload,) = daraja.stk_payloads()
    assert payload["BusinessShortCode"] == "174379" and payload["CallBackURL"] == GLOBAL_CALLBACK


def test_a_school_with_its_own_paybill_uses_its_own_credentials_shortcode_and_address(db, school_a, http, daraja):
    res = stk(http, school_a)
    assert res.status_code == 201, res.text
    stk_logins = daraja.oauth_logins()[-1]
    assert stk_logins == f"{A_KEY}:{A_SECRET}"
    payload = daraja.stk_payloads()[-1]
    assert payload["BusinessShortCode"] == "111111" and payload["PartyB"] == "111111"
    assert base64.b64decode(payload["Password"]).decode() == f"111111{A_PASSKEY}{payload['Timestamp']}"
    prefix = f"{ORIGIN}/api/payments/mpesa/callback?token="
    assert payload["CallBackURL"].startswith(prefix)
    assert accounts.verify_school_webhook_token(payload["CallBackURL"][len(prefix):]) == school_a.school.id


def test_each_school_pays_into_its_own_paybill_never_the_others(db, school_a, school_b, http, daraja):
    assert stk(http, school_a).status_code == 201
    assert stk(http, school_b).status_code == 201
    logins = daraja.oauth_logins()
    assert f"{A_KEY}:{A_SECRET}" in logins and f"{B_KEY}:{B_SECRET}" in logins
    by_code = {p["BusinessShortCode"]: p for p in daraja.stk_payloads()}
    assert set(by_code) == {"111111", "222222"}
    token_a = by_code["111111"]["CallBackURL"].split("token=")[1]
    token_b = by_code["222222"]["CallBackURL"].split("token=")[1]
    assert accounts.verify_school_webhook_token(token_a) == school_a.school.id
    assert accounts.verify_school_webhook_token(token_b) == school_b.school.id
    assert base64.b64decode(by_code["222222"]["Password"]).decode().startswith(f"222222{B_PASSKEY}")
    assert B_PASSKEY not in base64.b64decode(by_code["111111"]["Password"]).decode()


def test_saved_details_that_can_no_longer_be_read_stop_payments_cleanly(db, school_a, http, daraja):
    row = account_row(db, school_a.school)
    row.passkey_enc = "1.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    db.commit()
    res = stk(http, school_a)
    assert res.status_code == 503 and "isn't available" in res.json()["detail"]
    assert daraja.stk_payloads() == [] and db.execute(select(Payment)).first() is None
    assert http.get("/api/payments/mpesa/status", headers=school_a.headers).json() == {"enabled": False}


# ======================================================================================================
# STK callbacks: a school's address only affects that school
# ======================================================================================================


def _callback(http, checkout_id, token, amount=2000, receipt="RCPT0001"):
    body = {"Body": {"stkCallback": {
        "MerchantRequestID": "m", "CheckoutRequestID": checkout_id, "ResultCode": 0, "ResultDesc": "ok",
        "CallbackMetadata": {"Item": [{"Name": "Amount", "Value": amount}, {"Name": "MpesaReceiptNumber", "Value": receipt}]},
    }}}
    return http.post(f"/api/payments/mpesa/callback?token={token}", json=body)


def _pending(db, who):
    db.expire_all()
    return db.execute(select(Payment).where(Payment.school_id == who.school.id)).scalars().one()


def _token_from(daraja, index=-1):
    return daraja.stk_payloads()[index]["CallBackURL"].split("token=")[1]


def test_a_schools_own_address_confirms_that_schools_payment(db, school_a, http, daraja):
    assert stk(http, school_a).status_code == 201
    payment = _pending(db, school_a)
    assert _callback(http, payment.external_txn_id, _token_from(daraja)).status_code == 200
    assert _pending(db, school_a).status == PaymentStatus.CONFIRMED


def test_another_schools_address_cannot_confirm_this_schools_payment(db, school_a, school_b, http, daraja):
    assert stk(http, school_a).status_code == 201
    assert stk(http, school_b).status_code == 201
    token_b = _token_from(daraja)  # school B's (the last push)
    pay_a = _pending(db, school_a)
    assert _callback(http, pay_a.external_txn_id, token_b).status_code == 403
    assert _pending(db, school_a).status == PaymentStatus.PENDING  # untouched
    assert _pending(db, school_b).status == PaymentStatus.PENDING


def test_the_server_wide_secret_still_works_for_any_schools_payment(db, school_a, http, daraja):
    assert stk(http, school_a).status_code == 201
    assert _callback(http, _pending(db, school_a).external_txn_id, "global-secret-token-123456789").status_code == 200
    assert _pending(db, school_a).status == PaymentStatus.CONFIRMED


def test_a_rotated_or_forged_school_address_stops_working(db, school_a, http, daraja):
    assert stk(http, school_a).status_code == 201
    checkout = _pending(db, school_a).external_txn_id
    good = _token_from(daraja)
    school_id, version, mac = good.split(".")
    assert _callback(http, checkout, f"{school_id}.{version}.{'0' * len(mac)}").status_code == 403  # forged
    assert _callback(http, checkout, f"{school_id}.2.{mac}").status_code == 403  # wrong version
    assert _callback(http, checkout, "not-a-token").status_code == 403
    row = account_row(db, school_a.school)
    row.callback_token_version = 2  # rotation: the address Safaricom holds is now dead
    db.commit()
    assert _callback(http, checkout, good).status_code == 403
    assert _pending(db, school_a).status == PaymentStatus.PENDING


# ======================================================================================================
# Direct paybill payments: routed by the paybill they were paid to
# ======================================================================================================


def _c2b(http, token, shortcode, bill_ref, amount="1500", trans_id=None):
    return http.post(
        f"/api/payments/c2b/confirmation?token={token}",
        json={"TransID": trans_id or f"TX{uuid.uuid4().hex[:8].upper()}", "TransTime": "20261101120000", "TransAmount": amount,
              "BusinessShortCode": shortcode, "BillRefNumber": bill_ref, "MSISDN": "254712345678", "FirstName": "Pat"},
    )


def _school_token(school, version=1):
    return accounts.school_webhook_token(school.id, version)


def _payments_for(db, who):
    db.expire_all()
    return db.execute(select(Payment).where(Payment.school_id == who.school.id, Payment.status == PaymentStatus.CONFIRMED)).scalars().all()


def test_a_payment_to_a_schools_paybill_is_credited_to_that_schools_student_even_when_admission_numbers_repeat(db, school_a, school_b, http):
    # BOTH schools have a student 1001. The paybill tells them apart.
    assert _c2b(http, _school_token(school_a.school), "111111", "1001", amount="1500").status_code == 200
    assert _c2b(http, _school_token(school_b.school), "222222", "1001", amount="2500").status_code == 200
    (pa,), (pb,) = _payments_for(db, school_a), _payments_for(db, school_b)
    assert pa.amount == Decimal("1500") and pa.student_id == school_a.student.id
    assert pb.amount == Decimal("2500") and pb.student_id == school_b.student.id


def test_the_same_payment_is_not_matched_to_the_other_school_when_only_that_school_has_the_student(db, school_a, school_b, http):
    other = db.get(Student, school_b.student.id)
    other.admission_number = "7777"  # only school B has 7777
    db.commit()
    assert _c2b(http, _school_token(school_a.school), "111111", "7777").status_code == 200
    assert _payments_for(db, school_a) == [] and _payments_for(db, school_b) == []
    txn = db.execute(select(MpesaTransaction)).scalars().one()
    assert txn.school_id == school_a.school.id  # filed under the school whose paybill it was, waiting for ITS bursar
    assert txn.business_shortcode == "111111" and txn.status.value == "UNMATCHED"


def test_a_payment_to_a_paybill_that_belongs_to_nobody_here_is_ignored(db, school_a, http):
    assert _c2b(http, _school_token(school_a.school), "999999", "1001").status_code == 200
    assert db.execute(select(MpesaTransaction)).first() is None
    assert _payments_for(db, school_a) == []
    assert _c2b(http, "global-secret-token-123456789", "999999", "1001").status_code == 200
    assert db.execute(select(MpesaTransaction)).first() is None


def test_one_schools_address_cannot_report_a_payment_to_another_schools_paybill(db, school_a, school_b, http):
    res = _c2b(http, _school_token(school_a.school), "222222", "1001")  # A's token, B's paybill
    assert res.status_code == 403
    assert db.execute(select(MpesaTransaction)).first() is None and _payments_for(db, school_b) == []


def test_the_server_wide_paybill_only_matches_schools_that_use_it(db, school_a, world, http, monkeypatch):
    other = make_school(db, "Global School", mode="GLOBAL", admission="1001")  # also has a student 1001
    use_global_mpesa(db, other.school, monkeypatch)
    # school_a is on its OWN paybill, so a payment to the server-wide paybill must not be credited to its 1001.
    assert _c2b(http, "global-secret-token-123456789", "174379", "1001").status_code == 200
    assert _payments_for(db, school_a) == []
    (paid,) = _payments_for(db, other)
    assert paid.student_id == other.student.id


def test_two_schools_sharing_the_server_wide_paybill_with_the_same_admission_number_are_not_guessed_between(db, world, http, monkeypatch):
    other = make_school(db, "Second Global", mode="GLOBAL", admission="1001")
    use_global_mpesa(db, world.school, monkeypatch)
    assert _c2b(http, "global-secret-token-123456789", "174379", "1001").status_code == 200
    assert _payments_for(db, SimpleNamespace(school=world.school)) == [] and _payments_for(db, other) == []
    assert db.execute(select(MpesaTransaction)).scalars().one().status.value == "UNMATCHED"


def test_an_unmatched_payment_can_only_be_claimed_by_the_school_it_was_paid_to(db, school_a, school_b, http):
    db.get(Student, school_b.student.id).admission_number = "7777"
    db.commit()
    _c2b(http, _school_token(school_a.school), "111111", "7777", trans_id="LOOKUP01")
    assert http.get("/api/payments/mpesa/reconciliation/lookup?trans_id=LOOKUP01", headers=school_b.headers).status_code == 404
    assert http.get("/api/payments/mpesa/reconciliation/lookup?trans_id=LOOKUP01", headers=school_a.headers).status_code == 200
    txn = db.execute(select(MpesaTransaction)).scalars().one()
    assert http.post(f"/api/payments/mpesa/reconciliation/{txn.id}/match", headers=school_b.headers, json={"invoice_id": school_b.invoice.id}).status_code == 404
    assert http.post(f"/api/payments/mpesa/reconciliation/{txn.id}/match", headers=school_a.headers, json={"invoice_id": school_a.invoice.id}).status_code in (200, 201)


def test_sandbox_schools_sharing_the_public_test_shortcode_are_told_apart_by_their_address(db, world, http, operator, daraja):
    other = make_school(db, "Sandbox B", admission="1001")
    for who, key in ((world.school, "A"), (other.school, "B")):
        save_account(http, operator, who, shortcode="600000", key=f"KEY{key}-1234567", secret=f"SEC{key}-1234567", passkey=f"PASS{key}-1234567", environment="SANDBOX")
        http.post(f"/api/platform/schools/{who.id}/mpesa/test", headers=operator.headers)
        http.post(f"/api/platform/schools/{who.id}/mpesa/mode", headers=operator.headers, json={"mode": "OWN"})
    assert _c2b(http, _school_token(other.school), "600000", "1001").status_code == 200
    assert _payments_for(db, SimpleNamespace(school=world.school)) == []
    (paid,) = _payments_for(db, other)
    assert paid.student_id == other.student.id


def test_the_paybill_validation_address_authenticates_too(db, school_a, http):
    ok = http.post(f"/api/payments/c2b/validation?token={_school_token(school_a.school)}", json={})
    assert ok.status_code == 200 and ok.json()["ResultCode"] == 0
    assert http.post("/api/payments/c2b/validation?token=wrong", json={}).status_code == 403

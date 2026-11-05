"""Consent at sign-up, unsubscribe from optional email, and erasing your own account."""

import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.legal import TERMS_VERSION
from app.core.rate_limit import limiter
from app.core.security import create_access_token, decode_access_token, hash_password
from app.core.unsubscribe import create_unsubscribe_token, decode_unsubscribe_token
from app.main import app
from app.models.enums import GuardianLinkStatus
from app.models.job import Job
from app.models.message import Message
from app.models.payment import AuditLog
from app.models.school import School, User
from app.models.student import GuardianInvite, StudentGuardian
from app.services import job_handlers
from app.services.job_handlers import guardian_message_jobs
from tests.conftest import install_phone_key_function, needs_db

pytestmark = needs_db

PASSWORD = "Passw0rd!"


@pytest.fixture()
def http(db):
    limiter.reset()
    yield TestClient(app)
    limiter.reset()


def _signup_body(**over):
    body = {
        "full_name": "Pat Parent", "email": "pat@example.com", "phone": "0712345678", "password": PASSWORD,
        "accept_terms": True, "confirm_guardian": True,
    }
    body.update(over)
    return body


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.school_id, user.role.value, user.token_version)}"}


# ---- consent at sign-up ----------------------------------------------------------------------------


def test_parent_signup_without_accepting_the_terms_is_refused(db, world, http):
    install_phone_key_function(db)
    res = http.post("/api/auth/register-parent", json=_signup_body(accept_terms=False))
    assert res.status_code == 400 and "Terms" in res.json()["detail"]
    assert db.execute(select(User).where(User.email == "pat@example.com")).first() is None


def test_parent_signup_without_the_guardian_confirmation_is_refused(db, world, http):
    install_phone_key_function(db)
    res = http.post("/api/auth/register-parent", json=_signup_body(confirm_guardian=False))
    assert res.status_code == 400 and "guardian" in res.json()["detail"]
    assert db.execute(select(User).where(User.email == "pat@example.com")).first() is None


def test_boxes_default_to_not_accepted_when_the_client_leaves_them_out(db, world, http):
    install_phone_key_function(db)
    body = _signup_body()
    del body["accept_terms"], body["confirm_guardian"]
    assert http.post("/api/auth/register-parent", json=body).status_code == 400


def test_parent_signup_records_when_and_what_they_accepted(db, world, http):
    install_phone_key_function(db)
    assert http.post("/api/auth/register-parent", json=_signup_body()).status_code == 201
    user = db.execute(select(User).where(User.email == "pat@example.com")).scalar_one()
    assert user.terms_accepted_at is not None and user.terms_version == TERMS_VERSION


def test_creating_the_first_school_needs_the_terms_accepted(db, http):
    body = {
        "school_name": "First School", "country": "KE", "currency": "KES", "admin_email": "first@school.example",
        "admin_password": "Tr0ub4dor&3 horse", "admin_full_name": "First Admin",
    }
    assert http.post("/api/auth/register-school", json=body).status_code == 400
    assert db.execute(select(School)).first() is None
    assert http.post("/api/auth/register-school", json={**body, "accept_terms": True}).status_code == 201


def test_google_cannot_create_a_new_parent_account_without_consent(db, world, http, monkeypatch):
    from app.core.config import settings
    from app.routers import auth as auth_router

    monkeypatch.setattr(settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(
        auth_router.google_id_token, "verify_oauth2_token",
        lambda *a, **k: {"email": "new.google@example.com", "email_verified": True, "name": "New Google"},
    )
    res = http.post("/api/auth/google", json={"credential": "x"})
    assert res.status_code == 400
    assert db.execute(select(User).where(User.email == "new.google@example.com")).first() is None
    ok = http.post("/api/auth/google", json={"credential": "x", "accept_terms": True, "confirm_guardian": True})
    assert ok.status_code == 200
    assert db.execute(select(User.terms_version).where(User.email == "new.google@example.com")).scalar_one() == TERMS_VERSION


def test_google_sign_in_for_an_existing_account_needs_no_consent_boxes(db, world, http, monkeypatch):
    from app.core.config import settings
    from app.routers import auth as auth_router

    monkeypatch.setattr(settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(
        auth_router.google_id_token, "verify_oauth2_token",
        lambda *a, **k: {"email": world.parent.email, "email_verified": True, "name": "Parent"},
    )
    assert http.post("/api/auth/google", json={"credential": "x"}).status_code == 200


# ---- unsubscribe ------------------------------------------------------------------------------------


def test_unsubscribe_token_round_trips_and_is_useless_as_a_login_token(world):
    token = create_unsubscribe_token(world.parent.id)
    assert decode_unsubscribe_token(token) == world.parent.id
    with pytest.raises(ValueError):
        decode_access_token(token)
    with pytest.raises(ValueError):
        decode_unsubscribe_token("garbage")
    # a real login token is not an unsubscribe token either
    login = create_access_token(world.parent.id, world.parent.school_id, "PARENT", 0)
    with pytest.raises(ValueError):
        decode_unsubscribe_token(login)


def test_unsubscribe_then_resubscribe(db, world, http):
    token = create_unsubscribe_token(world.parent.id)
    assert http.post("/api/privacy/unsubscribe", json={"token": token}).json() == {"email_opt_out": True}
    db.expire_all()
    assert db.get(User, world.parent.id).email_opt_out is True
    assert http.post("/api/privacy/resubscribe", json={"token": token}).json() == {"email_opt_out": False}
    db.expire_all()
    assert db.get(User, world.parent.id).email_opt_out is False


def test_one_click_unsubscribe_from_the_mail_app(db, world, http):
    token = create_unsubscribe_token(world.parent.id)
    assert http.post(f"/api/privacy/unsubscribe/one-click?token={token}").status_code == 200
    db.expire_all()
    assert db.get(User, world.parent.id).email_opt_out is True


def test_a_bad_unsubscribe_link_is_refused(http):
    assert http.post("/api/privacy/unsubscribe", json={"token": "not-a-real-token"}).status_code == 400


def test_signed_in_parent_can_switch_optional_email_off_and_on(db, world, http):
    headers = _auth(world.parent)
    assert http.put("/api/privacy/me/email-preferences", json={"email_opt_out": True}, headers=headers).json()["email_opt_out"] is True
    assert http.get("/api/privacy/me", headers=headers).json()["email_opt_out"] is True
    assert http.put("/api/privacy/me/email-preferences", json={"email_opt_out": False}, headers=headers).json()["email_opt_out"] is False


def _capture_email(monkeypatch):
    sent = []
    monkeypatch.setattr(job_handlers, "send_email", lambda to, subject, body, headers=None: sent.append((to, subject, body, headers)))
    return sent


def test_optional_email_carries_an_unsubscribe_link_and_headers(db, world, monkeypatch):
    sent = _capture_email(monkeypatch)
    job_handlers.handle_send_email({"user_id": world.parent.id, "subject": "Fee reminder", "body": "Please pay.", "optional": True})
    assert len(sent) == 1
    to, _subject, body, headers = sent[0]
    assert to == world.parent.email and "/unsubscribe?token=" in body and "Payment receipts" in body
    assert headers and "List-Unsubscribe" in headers


def test_optional_email_is_not_sent_to_someone_who_unsubscribed(db, world, monkeypatch):
    sent = _capture_email(monkeypatch)
    world.parent.email_opt_out = True
    db.commit()
    job_handlers.handle_send_email({"user_id": world.parent.id, "subject": "Fee reminder", "body": "Please pay.", "optional": True})
    assert sent == []


def test_payment_receipts_are_always_sent_and_have_no_unsubscribe_footer(db, world, monkeypatch):
    sent = _capture_email(monkeypatch)
    world.parent.email_opt_out = True
    db.commit()
    job_handlers.handle_send_email({"user_id": world.parent.id, "subject": "Payment received", "body": "Thanks.", "optional": False})
    assert len(sent) == 1 and sent[0][2] == "Thanks." and sent[0][3] is None


def test_reminder_and_announcement_jobs_are_optional_but_receipts_are_not():
    reminder = guardian_message_jobs(school_id="s", guardian_id="g", email_subject="a", email_body="b", sms_text="c", dedupe_prefix="x")
    assert reminder[0]["payload"]["optional"] is True
    receipt = guardian_message_jobs(school_id="s", guardian_id="g", email_subject="a", email_body="b", sms_text="c", dedupe_prefix="x", optional=False)
    assert receipt[0]["payload"]["optional"] is False


def test_the_payment_result_job_queues_non_optional_email(db, world):
    from app.models.payment import Payment
    from app.models.enums import PaymentMethod, PaymentStatus

    db.add(StudentGuardian(student_id=world.student.id, user_id=world.parent.id, relationship_type="mother", status=GuardianLinkStatus.APPROVED))
    payment = Payment(
        school_id=world.school.id, student_id=world.student.id, invoice_id=world.invoice.id, amount=Decimal("500.00"),
        method=PaymentMethod.CASH, status=PaymentStatus.CONFIRMED,
    )
    db.add(payment)
    db.commit()
    job_handlers.handle_notify_payment_result({"payment_id": payment.id, "succeeded": True})
    db.expire_all()
    emails = [j for j in db.execute(select(Job).where(Job.kind == "send_email")).scalars()]
    assert emails and all(j.payload["optional"] is False for j in emails)


# ---- erasing your own account -----------------------------------------------------------------------


@pytest.fixture()
def parent_with_data(db, world):
    install_phone_key_function(db)
    world.parent.password_hash = hash_password(PASSWORD)
    world.parent.phone = "254712345678"
    db.add(StudentGuardian(student_id=world.student.id, user_id=world.parent.id, relationship_type="mother", status=GuardianLinkStatus.APPROVED))
    db.add(GuardianInvite(
        school_id=world.school.id, student_id=world.student.id, phone="0712345678", email=world.parent.email,
        full_name="Parent", relationship_type="mother",
    ))
    db.commit()
    return world.parent


def test_a_parent_can_erase_their_account(db, world, http, parent_with_data):
    parent_id, old_email = parent_with_data.id, parent_with_data.email
    res = http.post("/api/privacy/me/delete-account", json={"password": PASSWORD, "confirm": "DELETE"}, headers=_auth(parent_with_data))
    assert res.status_code == 200, res.text
    db.expire_all()
    user = db.get(User, parent_id)
    assert user.deleted_at is not None and user.is_active is False
    assert user.full_name == "Deleted user" and user.phone is None
    assert user.email != old_email and user.email.endswith("@deleted.ledgr.invalid")
    assert db.execute(select(StudentGuardian).where(StudentGuardian.user_id == parent_id)).first() is None
    assert db.execute(select(GuardianInvite)).first() is None
    # the money records survive; only the person is gone
    assert world.invoice.total_amount == Decimal("10000.00")
    assert db.execute(select(AuditLog).where(AuditLog.action == "ACCOUNT_ERASED")).scalar_one().entity_id == parent_id


def test_an_erased_account_can_no_longer_sign_in_or_use_old_tokens(db, world, http, parent_with_data):
    headers = _auth(parent_with_data)
    assert http.post("/api/privacy/me/delete-account", json={"password": PASSWORD, "confirm": "DELETE"}, headers=headers).status_code == 200
    assert http.post("/api/auth/login", json={"email": "pat@example.com", "password": PASSWORD}).status_code == 401
    assert http.get("/api/parent/students", headers=headers).status_code == 401


def test_erasing_removes_the_parents_messages_to_the_school(db, world, http, parent_with_data):
    from app.models.enums import MessageSenderRole

    db.add(Message(school_id=world.school.id, parent_user_id=parent_with_data.id, sender_user_id=parent_with_data.id,
                   sender_role=MessageSenderRole.PARENT, body="Can I pay in two instalments?"))
    db.commit()
    http.post("/api/privacy/me/delete-account", json={"password": PASSWORD, "confirm": "DELETE"}, headers=_auth(parent_with_data))
    db.expire_all()
    assert db.execute(select(Message)).first() is None


def test_erasure_needs_the_password_and_the_typed_word(db, world, http, parent_with_data):
    headers = _auth(parent_with_data)
    assert http.post("/api/privacy/me/delete-account", json={"password": "wrong", "confirm": "DELETE"}, headers=headers).status_code == 401
    assert http.post("/api/privacy/me/delete-account", json={"password": PASSWORD, "confirm": "yes"}, headers=headers).status_code == 400
    db.expire_all()
    assert db.get(User, parent_with_data.id).deleted_at is None


def test_staff_cannot_use_the_parent_erasure_endpoint(db, world, http):
    res = http.post("/api/privacy/me/delete-account", json={"password": PASSWORD, "confirm": "DELETE"}, headers=_auth(world.bursar))
    assert res.status_code == 403

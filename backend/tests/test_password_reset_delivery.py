"""Forgot-password must answer instantly and never 500 because a mail provider is down:
the email is queued and sent by the job worker, which retries."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.models.job import Job
from app.services import job_handlers
from tests.conftest import needs_db

pytestmark = needs_db


@pytest.fixture()
def client(db, world):
    from app.core.rate_limit import limiter

    limiter.reset()
    yield TestClient(app)
    limiter.reset()


def _jobs(db):
    db.expire_all()
    return db.execute(select(Job).where(Job.kind == "password_reset")).scalars().all()


def test_request_queues_a_job_and_sends_nothing_inline(db, world, client, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the request itself must not talk to the mail provider")

    monkeypatch.setattr(job_handlers, "send_email", boom)
    res = client.post("/api/auth/forgot-password", json={"email": world.parent.email})
    assert res.status_code == 200
    jobs = _jobs(db)
    assert len(jobs) == 1
    assert jobs[0].payload == {"user_id": world.parent.id, "channel": "email"}
    assert "token" not in str(jobs[0].payload)  # no live reset token sits in the queue


def test_unknown_email_gets_the_same_answer_and_queues_nothing(db, world, client):
    known = client.post("/api/auth/forgot-password", json={"email": world.parent.email})
    unknown = client.post("/api/auth/forgot-password", json={"email": "nobody@test.example"})
    assert (known.status_code, known.json()) == (unknown.status_code, unknown.json())
    assert len(_jobs(db)) == 1  # only the real account


def test_double_click_sends_once(db, world, client):
    for _ in range(3):
        assert client.post("/api/auth/forgot-password", json={"email": world.parent.email}).status_code == 200
    assert len(_jobs(db)) == 1


def test_inactive_account_gets_nothing(db, world, client):
    world.parent.is_active = False
    db.commit()
    assert client.post("/api/auth/forgot-password", json={"email": world.parent.email}).status_code == 200
    assert len(_jobs(db)) == 0


def test_handler_builds_a_fresh_link_and_emails_it(db, world, monkeypatch):
    sent = []
    monkeypatch.setattr(job_handlers, "send_email", lambda to, subject, body: sent.append((to, subject, body)))
    job_handlers.handle_password_reset({"user_id": world.parent.id, "channel": "email"})
    to, subject, body = sent[0]
    assert to == world.parent.email and "Reset your Ledgr password" in subject
    assert "/reset-password?token=" in body


def test_handler_failure_propagates_so_the_queue_retries(db, world, monkeypatch):
    def down(*a, **k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(job_handlers, "send_email", down)
    with pytest.raises(RuntimeError):
        job_handlers.handle_password_reset({"user_id": world.parent.id, "channel": "email"})


def test_handler_with_email_unconfigured_does_not_raise(db, world, monkeypatch):
    from app.services.notification_service import NotificationConfigError

    def unconfigured(*a, **k):
        raise NotificationConfigError("no provider")

    monkeypatch.setattr(job_handlers, "send_email", unconfigured)
    job_handlers.handle_password_reset({"user_id": world.parent.id, "channel": "email"})  # logs, doesn't retry forever


def test_account_without_a_school_is_not_dropped(db, world, client, monkeypatch):
    from app.models.enums import UserRole
    from app.models.school import User

    admin = User(school_id=None, email="root@test.example", password_hash="x", role=UserRole.SUPER_ADMIN, full_name="Root")
    db.add(admin)
    db.commit()
    submitted = []
    monkeypatch.setattr("app.routers.auth.background.submit", lambda fn, *a: submitted.append((fn, a)))
    assert client.post("/api/auth/forgot-password", json={"email": admin.email}).status_code == 200
    assert submitted == [(job_handlers.deliver_password_reset, (admin.id, "email"))]
    assert db.scalar(select(func.count()).select_from(Job)) == 0

"""The platform operator must have two-factor sign-in on, and cannot read a school's ledger."""

import uuid

import pyotp
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.deps import OPERATOR_2FA_MESSAGE
from app.core.security import create_access_token
from app.main import app
from app.core.totp import generate_totp_secret
from app.models.enums import UserRole
from app.models.school import User
from tests.conftest import needs_db


@pytest.fixture()
def http(db, world):
    from app.core.rate_limit import limiter

    limiter.reset()
    yield TestClient(app)
    limiter.reset()


def _operator(db, *, totp: bool) -> tuple[User, dict]:
    op = User(
        school_id=None,
        email=f"op-{uuid.uuid4().hex[:6]}@ledgr.test",
        password_hash="x",
        role=UserRole.SUPER_ADMIN,
        full_name="Operator",
        is_active=True,
        totp_enabled=totp,
        totp_secret=generate_totp_secret() if totp else None,
    )
    db.add(op)
    db.commit()
    return op, {"Authorization": "Bearer " + create_access_token(op.id, None, "SUPER_ADMIN", op.token_version or 0)}


def test_two_factor_is_required_by_default():
    assert settings.platform_require_2fa is True


@needs_db
def test_an_operator_without_two_factor_is_refused_on_every_platform_route(db, world, http):
    _op, headers = _operator(db, totp=False)
    sid = world.school.id
    calls = [
        ("GET", "/api/platform/schools", None),
        ("POST", "/api/platform/schools", {"school_name": "X", "admin_full_name": "A", "admin_email": "a@x.example"}),
        ("PATCH", f"/api/platform/schools/{sid}/subscription", {"extend_months": 1}),
        ("GET", f"/api/platform/schools/{sid}/mpesa", None),
        ("PUT", f"/api/platform/schools/{sid}/mpesa", {"environment": "SANDBOX", "shortcode": "174379", "consumer_key": "k", "consumer_secret": "s", "passkey": "p"}),
        ("DELETE", f"/api/platform/schools/{sid}/mpesa", None),
        ("POST", f"/api/platform/schools/{sid}/mpesa/test", None),
        ("POST", f"/api/platform/schools/{sid}/mpesa/register-urls", None),
        ("POST", f"/api/platform/schools/{sid}/mpesa/mode", {"mode": "OFF"}),
    ]
    for method, url, body in calls:
        res = http.request(method, url, json=body, headers=headers)
        assert res.status_code == 403, (method, url, res.status_code, res.text)
        assert res.json()["detail"] == OPERATOR_2FA_MESSAGE, (method, url)


@needs_db
def test_an_operator_with_two_factor_can_use_the_platform_routes(db, world, http):
    _op, headers = _operator(db, totp=True)
    res = http.get("/api/platform/schools", headers=headers)
    assert res.status_code == 200 and [r["id"] for r in res.json()] == [world.school.id]


@needs_db
def test_turning_two_factor_off_locks_the_platform_again_immediately(db, world, http):
    op, headers = _operator(db, totp=True)
    assert http.get("/api/platform/schools", headers=headers).status_code == 200
    op.totp_enabled = False
    db.commit()
    assert http.get("/api/platform/schools", headers=headers).status_code == 403


@needs_db
def test_the_operator_can_set_two_factor_up_and_then_use_the_platform(db, world, http):
    op, headers = _operator(db, totp=False)
    assert http.get("/api/platform/schools", headers=headers).status_code == 403

    assert http.get("/api/auth/2fa/status", headers=headers).json() == {"enabled": False}
    setup = http.post("/api/auth/2fa/setup", headers=headers)
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]

    assert http.post("/api/auth/2fa/enable", json={"code": "000000"}, headers=headers).status_code == 401
    enabled = http.post("/api/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=headers)
    assert enabled.status_code == 200, enabled.text

    assert http.get("/api/platform/schools", headers=headers).status_code == 200


@needs_db
def test_a_parent_still_cannot_touch_the_two_factor_setup_of_staff_routes(db, world, http):
    parent = {"Authorization": "Bearer " + create_access_token(world.parent.id, world.school.id, "PARENT", 0)}
    assert http.post("/api/auth/2fa/setup", headers=parent).status_code == 403


@needs_db
def test_the_operator_cannot_export_a_schools_ledger(db, world, http):
    _op, headers = _operator(db, totp=True)
    res = http.get(f"/api/reports/bursar-export?term_id={world.term.id}&format=csv", headers=headers)
    assert res.status_code == 400, res.text


@needs_db
def test_a_bursar_can_still_export_their_own_term_but_not_another_schools(db, world, http):
    from app.models.school import School, User
    from app.models.student import Term
    from datetime import datetime, timedelta, timezone

    own = {"Authorization": "Bearer " + create_access_token(world.bursar.id, world.school.id, "BURSAR", 0)}
    ok = http.get(f"/api/reports/bursar-export?term_id={world.term.id}&format=csv", headers=own)
    assert ok.status_code == 200, ok.text

    other = School(name="Other Academy", country="KE", contact_email="o@other.example")
    db.add(other)
    db.flush()
    other_term = Term(school_id=other.id, name="Term 9", start_date=datetime.now(timezone.utc), end_date=datetime.now(timezone.utc) + timedelta(days=90))
    db.add(other_term)
    db.commit()
    assert http.get(f"/api/reports/bursar-export?term_id={other_term.id}&format=csv", headers=own).status_code == 404

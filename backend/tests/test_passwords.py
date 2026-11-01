"""Password rules, hash strength, and quietly upgrading old hashes at login."""

import pytest
from fastapi.testclient import TestClient
from passlib.hash import bcrypt as raw_bcrypt
from pydantic import ValidationError
from sqlalchemy import select

from app.core import security
from app.core.rate_limit import limiter
from app.main import app
from app.models.enums import UserRole
from app.models.school import User
from app.schemas.auth import ResetPasswordRequest
from app.services.subscription_service import invalidate_school_state
from tests.conftest import needs_db


def _accepts(pw: str) -> bool:
    try:
        ResetPasswordRequest(token="t" * 20, new_password=pw)
        return True
    except ValidationError:
        return False


@pytest.mark.parametrize("pw", ["Tr0ub4dor&3 horse", "correct-horse-battery", "Ke!nya2026school", "ñandú-ñandú-99", "a" * 24 + "b"])
def test_reasonable_passwords_are_accepted(pw):
    assert _accepts(pw)


@pytest.mark.parametrize("pw", ["short", "1234567", "password", "Password1", "PASSWORD123", "qwerty123", "aaaaaaaaaaaa", "00000000"])
def test_short_common_or_repetitive_passwords_are_refused(pw):
    assert not _accepts(pw)


def test_a_password_longer_than_bcrypt_can_read_is_refused_rather_than_silently_truncated():
    assert _accepts("x1" * 36)  # exactly 72 bytes
    assert not _accepts("x1" * 36 + "y")  # 73
    assert not _accepts("é" * 37)  # 74 bytes but only 37 characters: the limit is bytes


def test_new_hashes_use_bcrypt_cost_12():
    assert security.hash_password("a-long-enough-password").startswith("$2b$12$")


def test_only_a_weaker_hash_is_flagged_for_an_upgrade():
    assert not security.password_needs_rehash(security.hash_password("pw-long-enough"))
    assert security.password_needs_rehash(raw_bcrypt.using(rounds=10).hash("pw-long-enough"))
    assert not security.password_needs_rehash("not-a-hash-at-all")  # never raises


# ---- login ----------------------------------------------------------------------------------------

pytestmark_db = needs_db


@pytest.fixture()
def http(db, world):
    limiter.reset()
    invalidate_school_state(world.school.id)
    yield TestClient(app)
    invalidate_school_state(world.school.id)
    limiter.reset()


def _user(db, world, email, pw, *, rounds=12, active=True):
    u = User(
        school_id=world.school.id, email=email, password_hash=raw_bcrypt.using(rounds=rounds).hash(pw),
        role=UserRole.PARENT, full_name="Pw Tester", is_active=active,
    )
    db.add(u)
    db.commit()
    return u


@needs_db
def test_an_older_weaker_hash_is_upgraded_the_next_time_they_sign_in(db, world, http):
    user = _user(db, world, "old@example.com", "Correct-Horse-9", rounds=10)
    assert user.password_hash.startswith("$2b$10$")
    assert http.post("/api/auth/login", json={"email": "old@example.com", "password": "Correct-Horse-9"}).status_code == 200
    db.expire_all()
    fresh = db.execute(select(User).where(User.email == "old@example.com")).scalar_one()
    assert fresh.password_hash.startswith("$2b$12$")
    assert security.verify_password("Correct-Horse-9", fresh.password_hash)  # and it still works
    assert http.post("/api/auth/login", json={"email": "old@example.com", "password": "Correct-Horse-9"}).status_code == 200


@needs_db
def test_a_wrong_password_never_changes_the_stored_hash(db, world, http):
    user = _user(db, world, "keep@example.com", "Correct-Horse-9", rounds=10)
    before = user.password_hash
    assert http.post("/api/auth/login", json={"email": "keep@example.com", "password": "Wrong-Horse-9"}).status_code == 401
    db.expire_all()
    assert db.execute(select(User.password_hash).where(User.email == "keep@example.com")).scalar_one() == before


@needs_db
def test_a_deactivated_account_still_costs_a_full_password_check(db, world, http, monkeypatch):
    """Otherwise a deactivated account answers measurably faster than a live one, which tells an attacker
    the account exists."""
    from app.routers import auth as auth_router

    calls = []
    real = auth_router.verify_password
    monkeypatch.setattr(auth_router, "verify_password", lambda p, h: calls.append(1) or real(p, h))
    _user(db, world, "gone@example.com", "Correct-Horse-9", active=False)
    res = http.post("/api/auth/login", json={"email": "gone@example.com", "password": "Correct-Horse-9"})
    assert res.status_code == 401
    assert len(calls) == 1

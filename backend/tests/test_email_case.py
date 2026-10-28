"""Emails are one identity whatever their capitalisation: sign-up, sign-in and staff creation all agree."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.rate_limit import limiter
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.enums import UserRole
from app.models.school import User
from app.services.subscription_service import invalidate_school_state
from tests.conftest import install_phone_key_function, needs_db

pytestmark = needs_db

PASSWORD = "Passw0rd!"


@pytest.fixture()
def http(db, world):
    install_phone_key_function(db)
    limiter.reset()
    invalidate_school_state(world.school.id)
    c = TestClient(app)
    yield c
    invalidate_school_state(world.school.id)
    limiter.reset()


def _signup(http, email, phone="0712345678"):
    return http.post(
        "/api/auth/register-parent",
        json={"full_name": "Pat Parent", "email": email, "phone": phone, "password": PASSWORD},
    )


def _login(http, email):
    return http.post("/api/auth/login", json={"email": email, "password": PASSWORD})


def test_signing_up_stores_the_email_in_lower_case_and_any_capitalisation_signs_in(db, world, http):
    assert _signup(http, "Pat.Parent@Example.COM").status_code == 201
    stored = db.execute(select(User).where(User.full_name == "Pat Parent")).scalar_one()
    assert stored.email == "pat.parent@example.com"
    for variant in ("pat.parent@example.com", "PAT.PARENT@EXAMPLE.COM", "Pat.Parent@Example.com"):
        assert _login(http, variant).status_code == 200, variant


def test_the_same_email_in_another_case_cannot_make_a_second_account(db, world, http):
    assert _signup(http, "pat@example.com").status_code == 201
    again = _signup(http, "PAT@Example.com", phone="0722000111")
    assert again.status_code == 409
    assert db.execute(select(User).where(User.full_name == "Pat Parent")).scalars().all().__len__() == 1


def test_an_older_mixed_case_account_can_still_sign_in_by_any_capitalisation(db, world, http):
    legacy = User(
        school_id=world.school.id, email="Legacy.User@Example.com", password_hash=hash_password(PASSWORD),
        role=UserRole.PARENT, full_name="Legacy", is_active=True,
    )
    db.add(legacy)
    db.commit()
    assert _login(http, "legacy.user@example.com").status_code == 200
    assert _login(http, "LEGACY.USER@EXAMPLE.COM").status_code == 200


def test_the_database_itself_refuses_two_accounts_that_differ_only_by_case(db, world):
    from sqlalchemy.exc import IntegrityError

    db.add(User(school_id=world.school.id, email="one@example.com", password_hash="x", role=UserRole.PARENT, full_name="A", is_active=True))
    db.commit()
    db.add(User(school_id=world.school.id, email="ONE@example.com", password_hash="x", role=UserRole.PARENT, full_name="B", is_active=True))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_creating_a_teacher_checks_for_an_existing_account_ignoring_case(db, world, http):
    admin = User(
        school_id=world.school.id, email="admin@example.com", password_hash="x", role=UserRole.SCHOOL_ADMIN,
        full_name="Admin", is_active=True,
    )
    db.add(admin)
    db.commit()
    headers = {"Authorization": "Bearer " + create_access_token(admin.id, world.school.id, "SCHOOL_ADMIN")}
    first = http.post("/api/teachers", json={"full_name": "Tee Cher", "email": "Tee.Cher@Example.com"}, headers=headers)
    assert first.status_code == 201, first.text
    second = http.post("/api/teachers", json={"full_name": "Tee Two", "email": "tee.cher@example.com"}, headers=headers)
    assert second.status_code == 409

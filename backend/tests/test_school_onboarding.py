"""More than one school on one deployment: who a new parent belongs to, how the operator adds a school,
and the learner limit that a school's plan sets."""

import re
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.main import app
from app.models.enums import UserRole
from app.models.payment import AuditLog
from app.models.school import School, User
from app.models.student import GuardianInvite, Student
from app.routers.auth import _resolve_parent_school_id
from app.services.notification_service import NotificationConfigError
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


def _token(user_id, school_id, role):
    return {"Authorization": "Bearer " + create_access_token(user_id, school_id, role)}


def _second_school(db, name="Second Academy"):
    """A second school with one student, so an invite can point at it."""
    school = School(name=name, country="KE", contact_email=f"office-{uuid.uuid4().hex[:6]}@second.example")
    db.add(school)
    db.flush()
    student = Student(school_id=school.id, admission_number="2001", full_name="Other Kid")
    db.add(student)
    db.commit()
    return school, student


def _invite(db, school, student, *, phone=None, email=None):
    db.add(
        GuardianInvite(
            school_id=school.id, student_id=student.id, phone=phone, email=email,
            full_name="Expected Parent", relationship_type="mother",
        )
    )
    db.commit()


# ---- which school does a self-registering parent belong to? -------------------------------------


def test_one_school_on_the_deployment_is_the_obvious_answer(db, world):
    install_phone_key_function(db)
    assert _resolve_parent_school_id(db, "new@example.com", "254712345678") == world.school.id


def test_two_schools_and_no_invite_refuses_to_guess(db, world):
    install_phone_key_function(db)
    _second_school(db)
    with pytest.raises(HTTPException) as err:
        _resolve_parent_school_id(db, "new@example.com", "254712345678")
    assert err.value.status_code == 409


def test_an_invite_places_the_parent_by_phone_or_by_email_ignoring_case(db, world):
    install_phone_key_function(db)
    other, other_student = _second_school(db)
    _invite(db, other, other_student, phone="0712345678", email="Mum@Example.com")
    assert _resolve_parent_school_id(db, "someone-else@example.com", "254712345678") == other.id  # by phone
    assert _resolve_parent_school_id(db, "MUM@example.COM", None) == other.id  # by email


def test_invites_from_two_schools_for_the_same_contact_are_not_guessed_between(db, world):
    install_phone_key_function(db)
    other, other_student = _second_school(db)
    _invite(db, world.school, world.student, phone="0712345678")
    _invite(db, other, other_student, phone="0712345678")
    with pytest.raises(HTTPException) as err:
        _resolve_parent_school_id(db, "new@example.com", "254712345678")
    assert err.value.status_code == 409


def test_register_parent_joins_the_school_that_invited_them(db, world, http):
    other, other_student = _second_school(db)
    _invite(db, other, other_student, phone="0799111222")
    res = http.post(
        "/api/auth/register-parent",
        json={"full_name": "Invited Parent", "email": "invited@example.com", "phone": "0799111222", "password": PASSWORD},
    )
    assert res.status_code == 201, res.text
    assert db.execute(select(User.school_id).where(User.email == "invited@example.com")).scalar_one() == other.id


def test_register_parent_with_two_schools_and_no_invite_is_refused(db, world, http):
    _second_school(db)
    res = http.post(
        "/api/auth/register-parent",
        json={"full_name": "Lost Parent", "email": "lost@example.com", "phone": "0733000111", "password": PASSWORD},
    )
    assert res.status_code == 409
    assert db.execute(select(User).where(User.email == "lost@example.com")).first() is None


# ---- Google sign-in follows the same rule (it used to grab School.first()) ----------------------


@pytest.fixture()
def google(monkeypatch):
    from app.core.config import settings
    from app.routers import auth as auth_router

    monkeypatch.setattr(settings, "google_client_id", "test-client-id")
    state = {"email": "g.parent@example.com"}
    monkeypatch.setattr(
        auth_router.google_id_token,
        "verify_oauth2_token",
        lambda *a, **k: {"email": state["email"], "email_verified": True, "name": "G Parent"},
    )
    return state


def test_google_signup_with_two_schools_and_no_invite_is_refused(db, world, http, google):
    _second_school(db)
    res = http.post("/api/auth/google", json={"credential": "x"})
    assert res.status_code == 409
    assert db.execute(select(User).where(User.email == "g.parent@example.com")).first() is None


def test_google_signup_joins_the_school_that_invited_that_email(db, world, http, google):
    other, other_student = _second_school(db)
    _invite(db, other, other_student, email="G.Parent@Example.com")
    res = http.post("/api/auth/google", json={"credential": "x"})
    assert res.status_code in (200, 201), res.text
    assert db.execute(select(User.school_id).where(User.email == "g.parent@example.com")).scalar_one() == other.id


def test_google_signup_still_works_when_there_is_only_one_school(db, world, http, google):
    res = http.post("/api/auth/google", json={"credential": "x"})
    assert res.status_code in (200, 201), res.text
    assert db.execute(select(User.school_id).where(User.email == "g.parent@example.com")).scalar_one() == world.school.id


def test_google_matches_an_existing_account_whatever_the_capitalisation(db, world, http, google):
    google["email"] = "Existing.Person@Example.com"
    db.add(User(school_id=world.school.id, email="existing.person@example.com", password_hash="x", role=UserRole.PARENT, full_name="Existing", is_active=True))
    db.commit()
    res = http.post("/api/auth/google", json={"credential": "x"})
    assert res.status_code == 200
    assert db.execute(select(User).where(User.full_name == "G Parent")).first() is None  # no duplicate was made


# ---- the operator adds a school -----------------------------------------------------------------


@pytest.fixture()
def operator(db):
    op = User(school_id=None, email="operator@ledgr.test", password_hash="x", role=UserRole.SUPER_ADMIN, full_name="Operator", is_active=True)
    db.add(op)
    db.commit()
    return op, _token(op.id, None, "SUPER_ADMIN")


@pytest.fixture()
def mailbox(monkeypatch):
    """Captures what the platform router would email, instead of sending it."""
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr("app.routers.platform.send_email", lambda to, subject, body: sent.append((to, subject, body)))
    return sent


NEW_SCHOOL = {"school_name": "Brand New Academy", "admin_full_name": "Ada Admin", "admin_email": "Ada.Admin@NewSchool.example"}


def test_the_operator_can_add_a_school_and_its_admin_sets_their_own_password(db, world, http, operator, mailbox):
    _op, headers = operator
    res = http.post("/api/platform/schools", json={**NEW_SCHOOL, "trial_days": 30, "learner_limit": 150}, headers=headers)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "Brand New Academy"
    assert body["status"] == "TRIAL" and body["learner_limit"] == 150
    assert body["invite_sent"] is True and body["contact_email"] == "ada.admin@newschool.example"

    admin = db.execute(select(User).where(User.email == "ada.admin@newschool.example")).scalar_one()
    assert admin.role == UserRole.SCHOOL_ADMIN and admin.school_id == body["id"]
    assert db.execute(select(AuditLog).where(AuditLog.action == "SCHOOL_CREATED", AuditLog.school_id == body["id"])).scalar_one()

    # Nobody was handed a password. The email carries a link, and that link really works.
    assert len(mailbox) == 1 and mailbox[0][0] == "ada.admin@newschool.example"
    token = re.search(r"token=([\w\-.]+)", mailbox[0][2]).group(1)
    assert http.post("/api/auth/reset-password", json={"token": token, "new_password": "BrandNew#Pass1"}).status_code == 200
    login = http.post("/api/auth/login", json={"email": "ADA.ADMIN@newschool.example", "password": "BrandNew#Pass1"})
    assert login.status_code == 200
    # ...and that admin is inside the NEW school (its trial and learner limit), not the first one.
    mine = http.get("/api/subscription", headers={"Authorization": "Bearer " + login.json()["token"]}).json()
    assert mine["status"] == "TRIAL" and mine["learner_limit"] == 150 and mine["learner_count"] == 0


def test_the_new_school_is_listed_alongside_the_existing_one(db, world, http, operator, mailbox):
    _op, headers = operator
    http.post("/api/platform/schools", json=NEW_SCHOOL, headers=headers)
    names = {r["name"] for r in http.get("/api/platform/schools", headers=headers).json()}
    assert names == {"Test Academy", "Brand New Academy"}


def test_the_school_is_still_created_if_the_invite_email_cannot_be_sent(db, world, http, operator, monkeypatch):
    def broken(*a, **k):
        raise NotificationConfigError("no email configured")

    monkeypatch.setattr("app.routers.platform.send_email", broken)
    _op, headers = operator
    res = http.post("/api/platform/schools", json=NEW_SCHOOL, headers=headers)
    assert res.status_code == 201 and res.json()["invite_sent"] is False
    assert db.execute(select(School).where(School.name == "Brand New Academy")).scalar_one()


def test_an_email_that_already_has_an_account_cannot_be_the_new_admin_whatever_its_case(db, world, http, operator, mailbox):
    _op, headers = operator
    taken = {**NEW_SCHOOL, "admin_email": world.bursar.email.upper()}
    res = http.post("/api/platform/schools", json=taken, headers=headers)
    assert res.status_code == 409
    assert db.execute(select(School).where(School.name == "Brand New Academy")).first() is None  # nothing half-created


def test_only_the_operator_can_add_a_school(db, world, http, mailbox):
    for user, role in ((world.bursar, "BURSAR"), (world.parent, "PARENT")):
        res = http.post("/api/platform/schools", json=NEW_SCHOOL, headers=_token(user.id, world.school.id, role))
        assert res.status_code == 403
    assert http.post("/api/platform/schools", json=NEW_SCHOOL).status_code in (401, 403)
    assert db.execute(select(School).where(School.name == "Brand New Academy")).first() is None


def test_the_public_setup_endpoint_still_refuses_once_a_school_exists(db, world, http):
    res = http.post(
        "/api/auth/register-school",
        json={"school_name": "Sneaky School", "country": "KE", "currency": "KES", "admin_email": "sneaky@example.com", "admin_password": PASSWORD, "admin_full_name": "Sneaky"},
    )
    assert res.status_code == 403


# ---- the learner limit --------------------------------------------------------------------------


def _add_student(http, headers, n):
    return http.post("/api/students", json={"admission_number": f"L{n}", "full_name": f"Learner {n}"}, headers=headers)


def _limit(db, school_id, value):
    school = db.get(School, school_id)
    school.learner_limit = value
    db.commit()


def test_a_school_can_add_learners_up_to_its_limit_and_no_further(db, world, http):
    headers = _token(world.bursar.id, world.school.id, "BURSAR")
    _limit(db, world.school.id, 3)  # the world fixture already has one active learner
    assert _add_student(http, headers, 1).status_code == 201
    assert _add_student(http, headers, 2).status_code == 201
    blocked = _add_student(http, headers, 3)
    assert blocked.status_code == 402
    assert "3" in blocked.json()["detail"]
    assert db.execute(select(Student).where(Student.admission_number == "L3")).first() is None


def test_deactivating_a_learner_frees_a_place(db, world, http):
    headers = _token(world.bursar.id, world.school.id, "BURSAR")
    _limit(db, world.school.id, 2)
    created = _add_student(http, headers, 1)
    assert created.status_code == 201
    assert _add_student(http, headers, 2).status_code == 402
    assert http.post(f"/api/students/{created.json()['id']}/deactivate", headers=headers).status_code == 200
    assert _add_student(http, headers, 2).status_code == 201


def test_no_limit_means_no_cap(db, world, http):
    headers = _token(world.bursar.id, world.school.id, "BURSAR")
    _limit(db, world.school.id, None)
    assert all(_add_student(http, headers, n).status_code == 201 for n in range(5))


def test_lowering_the_limit_below_the_current_count_keeps_everyone_but_blocks_new_ones(db, world, http):
    headers = _token(world.bursar.id, world.school.id, "BURSAR")
    assert _add_student(http, headers, 1).status_code == 201
    assert _add_student(http, headers, 2).status_code == 201
    _limit(db, world.school.id, 1)  # 3 active learners now, limit 1
    assert _add_student(http, headers, 3).status_code == 402
    active = db.execute(select(Student).where(Student.school_id == world.school.id, Student.is_active == True)).scalars().all()  # noqa: E712
    assert len(active) == 3  # nobody was removed
    assert http.get("/api/subscription", headers=headers).json()["over_limit"] is True


def test_one_schools_limit_does_not_affect_another_school(db, world, http):
    other, _ = _second_school(db)
    _limit(db, other.id, 1)  # the other school is full
    headers = _token(world.bursar.id, world.school.id, "BURSAR")
    assert _add_student(http, headers, 1).status_code == 201

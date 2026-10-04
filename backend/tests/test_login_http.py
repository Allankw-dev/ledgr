"""Sign-in over HTTP: parents sharing an IP, and the per-account lock."""

import pytest
from fastapi.testclient import TestClient

from app.core import login_throttle as lt
from app.core.security import hash_password
from app.main import app
from app.models.enums import UserRole
from app.models.school import User
from tests.conftest import needs_db

pytestmark = needs_db


@pytest.fixture()
def client(db, world, monkeypatch):
    lt._local.clear()
    monkeypatch.setattr(lt, "_redis_client", lambda: None)
    world.parent.password_hash = hash_password("Passw0rd!")
    db.commit()
    from app.core.rate_limit import limiter
    limiter.reset()
    yield TestClient(app)
    lt._local.clear()
    limiter.reset()


def _login(client, email, password="Passw0rd!"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_many_different_parents_on_one_ip_can_all_sign_in(db, world, client):
    emails = []
    for i in range(15):  # 15 real parents, one shared address (school wifi / carrier NAT)
        u = User(school_id=world.school.id, email=f"p{i}@test.example", password_hash=hash_password("Passw0rd!"),
                 role=UserRole.PARENT, full_name=f"P{i}")
        db.add(u)
        emails.append(u.email)
    db.commit()
    codes = [_login(client, e).status_code for e in emails]
    assert codes == [200] * 15  # used to be 10 successes then 5 refusals


def test_guessing_one_account_gets_locked_even_with_the_right_password_afterwards(db, world, client):
    email = world.parent.email
    for _ in range(lt.MAX_FAILURES):
        assert _login(client, email, "wrong").status_code == 401
    locked = _login(client, email, "Passw0rd!")  # even the CORRECT password is refused while locked
    assert locked.status_code == 429 and "Too many failed attempts" in locked.json()["detail"]


def test_locking_one_account_does_not_touch_another(db, world, client):
    other = User(school_id=world.school.id, email="other@test.example", password_hash=hash_password("Passw0rd!"),
                 role=UserRole.PARENT, full_name="Other")
    db.add(other)
    db.commit()
    for _ in range(lt.MAX_FAILURES):
        _login(client, world.parent.email, "wrong")
    assert _login(client, other.email).status_code == 200


def test_a_few_typos_then_the_right_password_works_and_resets(db, world, client):
    for _ in range(lt.MAX_FAILURES - 1):
        _login(client, world.parent.email, "typo")
    assert _login(client, world.parent.email).status_code == 200
    for _ in range(lt.MAX_FAILURES - 1):  # the count started over
        _login(client, world.parent.email, "typo")
    assert _login(client, world.parent.email).status_code == 200

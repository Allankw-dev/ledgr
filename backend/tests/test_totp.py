import time

import pyotp
import pytest
from fastapi import HTTPException

from app.core import totp
from app.core.deps import CurrentUser
from app.routers import auth as auth_router
from tests.conftest import needs_db

SECRET = pyotp.random_base32()


def code_at(offset_steps: int) -> str:
    return pyotp.TOTP(SECRET).at(time.time() + offset_steps * 30)


def test_current_and_adjacent_codes_accepted():
    for step in (-1, 0, 1):
        assert totp.verify_totp_code(SECRET, code_at(step))


def test_code_from_a_clock_that_is_minutes_off_is_rejected():
    assert not totp.verify_totp_code(SECRET, code_at(5))
    assert not totp.verify_totp_code(SECRET, code_at(-5))


def test_code_with_a_space_or_garbage_is_normalised():
    c = code_at(0)
    assert totp.verify_totp_code(SECRET, f"{c[:3]} {c[3:]}")
    assert totp.verify_totp_code(SECRET, f" {c}\n")
    assert not totp.verify_totp_code(SECRET, "12345")
    assert not totp.verify_totp_code(SECRET, "")


def test_diagnose_reports_clock_offset_and_distinguishes_a_typo():
    assert totp.diagnose_failed_code(SECRET, code_at(4)) == 4
    assert totp.diagnose_failed_code(SECRET, code_at(-6)) == -6
    other = pyotp.TOTP(pyotp.random_base32()).now()  # a stale authenticator entry for a different secret
    # a code for some other secret matches no nearby step of this one (collision odds ~1 in 25,000)
    assert totp.diagnose_failed_code(SECRET, other) is None
    assert totp.diagnose_failed_code(SECRET, "abc") is None


@needs_db
def test_setup_refused_while_2fa_is_on_so_the_working_secret_is_not_overwritten(db, world):
    user = CurrentUser(user_id=world.bursar.id, school_id=world.school.id, role="BURSAR")
    first = auth_router.setup_2fa(db=db, user=user)
    code = pyotp.TOTP(first.secret).now()
    assert auth_router.enable_2fa(auth_router.TwoFactorEnableRequest(code=code), db=db, user=user) == {"enabled": True}

    with pytest.raises(HTTPException) as e:
        auth_router.setup_2fa(db=db, user=user)
    assert e.value.status_code == 409
    db.refresh(world.bursar)
    assert world.bursar.totp_secret == first.secret  # unchanged — their authenticator still works
    assert totp.verify_totp_code(world.bursar.totp_secret, pyotp.TOTP(first.secret).now())


@needs_db
def test_setup_can_be_redone_before_enabling(db, world):
    user = CurrentUser(user_id=world.bursar.id, school_id=world.school.id, role="BURSAR")
    a = auth_router.setup_2fa(db=db, user=user)
    b = auth_router.setup_2fa(db=db, user=user)  # half-finished setup, start over: allowed
    assert a.secret != b.secret

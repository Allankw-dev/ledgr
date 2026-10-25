"""A school's subscription: the rules, the everyday operator actions, and what staff vs parents can still do."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.main import app
from app.models.enums import UserRole
from app.models.payment import AuditLog
from app.models.school import School, User
from app.services.subscription_service import (
    GRACE_DAYS,
    SubscriptionState,
    add_months,
    apply_update,
    compute_state,
    invalidate_school_state,
)
from tests.conftest import needs_db

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
days = lambda n: timedelta(days=n)  # noqa: E731


# ---- the rules (no database needed) ----------------------------------------------------------


def test_a_school_with_no_dates_never_expires():
    assert compute_state("ACTIVE", None, None, NOW) == SubscriptionState("ACTIVE", False, None, None)


def test_in_date_then_grace_then_read_only():
    paid_until = NOW + days(10)
    assert compute_state("ACTIVE", None, paid_until, NOW).status == "ACTIVE"
    assert compute_state("ACTIVE", None, paid_until, NOW).days_left == 10

    just_past = compute_state("ACTIVE", None, NOW - days(1), NOW)
    assert (just_past.status, just_past.read_only) == ("GRACE", False)
    assert just_past.days_left == GRACE_DAYS - 1  # days until read-only starts

    long_past = compute_state("ACTIVE", None, NOW - days(GRACE_DAYS + 1), NOW)
    assert (long_past.status, long_past.read_only) == ("EXPIRED", True)


def test_trials_follow_the_trial_date_not_the_paid_date():
    assert compute_state("TRIAL", NOW + days(5), NOW - days(100), NOW).status == "TRIAL"
    assert compute_state("TRIAL", NOW - days(30), None, NOW).status == "EXPIRED"
    assert compute_state("TRIAL", None, None, NOW) == SubscriptionState("TRIAL", False, None, None)


def test_suspended_is_read_only_whatever_the_dates_say():
    state = compute_state("SUSPENDED", None, NOW + days(300), NOW)
    assert (state.status, state.read_only) == ("SUSPENDED", True)


def test_naive_dates_are_treated_as_utc():
    assert compute_state("ACTIVE", None, datetime(2026, 12, 1), NOW).status == "ACTIVE"


def test_add_months_clamps_to_the_end_of_a_short_month():
    assert add_months(datetime(2026, 1, 31, tzinfo=timezone.utc), 1) == datetime(2026, 2, 28, tzinfo=timezone.utc)
    assert add_months(datetime(2026, 11, 15, tzinfo=timezone.utc), 3) == datetime(2027, 2, 15, tzinfo=timezone.utc)


# ---- the operator's everyday actions ---------------------------------------------------------


@needs_db
def test_extending_adds_to_whichever_is_later_so_paying_early_loses_nothing(db, world):
    school = db.get(School, world.school.id)
    school.paid_until = NOW + days(40)
    db.commit()
    apply_update(db, school, operator_id=None, extend_months=4, now=NOW)
    assert school.paid_until == add_months(NOW + days(40), 4)
    assert school.subscription_status == "ACTIVE"


@needs_db
def test_extending_an_expired_or_suspended_school_starts_from_today_and_reactivates_it(db, world):
    school = db.get(School, world.school.id)
    school.subscription_status, school.paid_until = "SUSPENDED", NOW - days(200)
    db.commit()
    apply_update(db, school, operator_id=None, extend_months=1, now=NOW)
    assert (school.subscription_status, school.paid_until) == ("ACTIVE", add_months(NOW, 1))


@needs_db
def test_starting_a_trial_and_clearing_the_learner_limit(db, world):
    school = db.get(School, world.school.id)
    school.learner_limit = 300
    db.commit()
    apply_update(db, school, operator_id=None, trial_days=30, learner_limit=None, now=NOW)
    assert (school.subscription_status, school.trial_ends_at, school.learner_limit) == ("TRIAL", NOW + days(30), None)


@needs_db
def test_every_change_is_written_to_the_audit_log(db, world):
    school = db.get(School, world.school.id)
    apply_update(db, school, operator_id=None, status="SUSPENDED")
    row = db.execute(select(AuditLog).where(AuditLog.action == "SUBSCRIPTION_UPDATED")).scalar_one()
    assert row.log_metadata["before"]["status"] == "ACTIVE" and row.log_metadata["after"]["status"] == "SUSPENDED"


# ---- over HTTP --------------------------------------------------------------------------------


@pytest.fixture()
def http(db, world):
    from app.core.rate_limit import limiter

    limiter.reset()
    invalidate_school_state(world.school.id)
    c = TestClient(app)
    yield c
    invalidate_school_state(world.school.id)
    limiter.reset()


def _as(user_id, school_id, role):
    return {"Authorization": "Bearer " + create_access_token(user_id, school_id, role)}


def _expire(db, school_id):
    school = db.get(School, school_id)
    school.paid_until = datetime.now(timezone.utc) - days(GRACE_DAYS + 5)
    db.commit()
    invalidate_school_state(school_id)


TERM = {"name": "Term 9", "start_date": "2027-01-05T00:00:00Z", "end_date": "2027-04-01T00:00:00Z"}


@needs_db
def test_staff_can_still_read_but_not_change_anything_once_expired(db, world, http):
    bursar = _as(world.bursar.id, world.school.id, "BURSAR")
    assert http.post("/api/terms", json=TERM, headers=bursar).status_code == 201  # in good standing

    _expire(db, world.school.id)
    assert http.get("/api/terms", headers=bursar).status_code == 200
    blocked = http.post("/api/terms", json={**TERM, "name": "Term 10"}, headers=bursar)
    assert blocked.status_code == 402
    assert "read-only" in blocked.json()["detail"]


@needs_db
def test_renewing_unblocks_immediately(db, world, http):
    bursar = _as(world.bursar.id, world.school.id, "BURSAR")
    _expire(db, world.school.id)
    assert http.post("/api/terms", json=TERM, headers=bursar).status_code == 402
    apply_update(db, db.get(School, world.school.id), operator_id=None, extend_months=1)
    assert http.post("/api/terms", json=TERM, headers=bursar).status_code == 201


@needs_db
def test_a_parent_is_never_blocked_by_the_schools_subscription(db, world, http):
    _expire(db, world.school.id)
    parent = _as(world.parent.id, world.school.id, "PARENT")
    # Whatever this returns, it must not be the subscription block: parents keep being able to pay.
    res = http.post("/api/payments/mpesa/stk-push", json={"invoice_id": "does-not-exist", "phone_number": "0712345678"}, headers=parent)
    assert res.status_code != 402


@needs_db
def test_my_subscription_reports_the_standing_and_learner_usage(db, world, http):
    school = db.get(School, world.school.id)
    school.learner_limit = 0 + 1
    school.paid_until = datetime.now(timezone.utc) + days(20)
    db.commit()
    body = http.get("/api/subscription", headers=_as(world.bursar.id, world.school.id, "BURSAR")).json()
    assert body["status"] == "ACTIVE" and body["read_only"] is False
    assert body["learner_count"] >= 1 and body["learner_limit"] == 1
    assert body["days_left"] in (20, 21)
    assert http.get("/api/subscription", headers=_as(world.parent.id, world.school.id, "PARENT")).status_code == 403


@needs_db
def test_only_the_platform_operator_can_use_the_platform_endpoints(db, world, http):
    op = User(school_id=None, email="operator@ledgr.test", password_hash="x", role=UserRole.SUPER_ADMIN, full_name="Operator")
    db.add(op)
    db.commit()
    operator = _as(op.id, None, "SUPER_ADMIN")

    assert http.get("/api/platform/schools", headers=_as(world.bursar.id, world.school.id, "BURSAR")).status_code == 403
    assert http.get("/api/platform/schools", headers=_as(world.parent.id, world.school.id, "PARENT")).status_code == 403

    rows = http.get("/api/platform/schools", headers=operator).json()
    assert [r["id"] for r in rows] == [world.school.id] and rows[0]["status"] == "ACTIVE"

    res = http.patch(f"/api/platform/schools/{world.school.id}/subscription", json={"extend_months": 4, "learner_limit": 250}, headers=operator)
    assert res.status_code == 200
    assert res.json()["learner_limit"] == 250 and res.json()["days_left"] >= 119

    cleared = http.patch(f"/api/platform/schools/{world.school.id}/subscription", json={"learner_limit": None}, headers=operator).json()
    assert cleared["learner_limit"] is None

    assert http.patch("/api/platform/schools/nope/subscription", json={"status": "SUSPENDED"}, headers=operator).status_code == 404
    assert http.patch(f"/api/platform/schools/{world.school.id}/subscription", json={"status": "BANANAS"}, headers=operator).status_code == 422

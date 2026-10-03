from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text

from app.core import idempotency as idem
from app.models.idempotency import IdempotencyKey
from tests.conftest import needs_db

pytestmark = needs_db


def _kw(w, key="k1", body=None):
    return dict(school_id=w.school.id, user_id=w.parent.id, scope="mpesa.stk_push", key=key, request_body=body or {"a": 1})


def test_run_idempotent_replays_stored_response(db, world):
    calls = []

    def action():
        calls.append(1)
        return 201, {"n": len(calls)}

    first = idem.run_idempotent(db, action=action, **_kw(world))
    second = idem.run_idempotent(db, action=action, **_kw(world))
    assert len(calls) == 1
    assert first.status_code == second.status_code == 201
    assert second.headers["Idempotent-Replay"] == "true"
    assert second.body == first.body


def test_run_idempotent_same_key_different_body_is_422(db, world):
    idem.run_idempotent(db, action=lambda: (201, {}), **_kw(world))
    with pytest.raises(HTTPException) as e:
        idem.run_idempotent(db, action=lambda: (201, {}), **_kw(world, body={"a": 2}))
    assert e.value.status_code == 422


def test_run_idempotent_failure_rolls_back_key_so_retry_runs(db, world):
    def boom():
        raise RuntimeError("db hiccup")

    with pytest.raises(RuntimeError):
        idem.run_idempotent(db, action=boom, **_kw(world))
    assert db.execute(select(IdempotencyKey)).first() is None
    resp = idem.run_idempotent(db, action=lambda: (201, {"ok": True}), **_kw(world))
    assert resp.status_code == 201


def test_run_idempotent_without_key_just_runs(db, world):
    calls = []
    for _ in range(2):
        idem.run_idempotent(db, action=lambda: (calls.append(1) or (200, {})), **{**_kw(world), "key": None})
    assert len(calls) == 2


def test_key_is_scoped_per_user(db, world):
    calls = []
    for uid in (world.parent.id, world.bursar.id):
        idem.run_idempotent(db, action=lambda: (calls.append(1) or (200, {})), **{**_kw(world), "user_id": uid})
    assert len(calls) == 2


def test_overlong_key_rejected(db, world):
    with pytest.raises(HTTPException) as e:
        idem.run_idempotent(db, action=lambda: (200, {}), **_kw(world, key="x" * 201))
    assert e.value.status_code == 422


# --- reserve / store / release (the STK push path) ---------------------------


def test_reserve_then_store_then_replay(db, world):
    assert idem.reserve_key(db, **_kw(world)) is None  # fresh: caller does the work
    idem.store_result(db, school_id=world.school.id, user_id=world.parent.id, scope="mpesa.stk_push",
                      key="k1", status_code=201, response={"checkout_request_id": "ws_1"})
    kind, stored = idem.reserve_key(db, **_kw(world))
    assert kind == "replay" and stored == {"checkout_request_id": "ws_1"}


def test_second_request_while_first_in_flight_gets_409(db, world):
    assert idem.reserve_key(db, **_kw(world)) is None
    with pytest.raises(HTTPException) as e:
        idem.reserve_key(db, **_kw(world))
    assert e.value.status_code == 409


def test_release_lets_a_retry_through(db, world):
    idem.reserve_key(db, **_kw(world))
    idem.release_key(db, school_id=world.school.id, user_id=world.parent.id, scope="mpesa.stk_push", key="k1")
    assert idem.reserve_key(db, **_kw(world)) is None


def _backdate(db, seconds):
    db.execute(text("UPDATE idempotency_keys SET created_at = now() - make_interval(secs => :s)"), {"s": seconds})
    db.commit()


def test_abandoned_reservation_is_taken_over_after_stale_window(db, world):
    """A worker that crashed between the Daraja call and store_result must not lock the key for 24h."""
    idem.reserve_key(db, **_kw(world))
    _backdate(db, idem.STALE_RESERVATION.total_seconds() + 30)
    assert idem.reserve_key(db, **_kw(world)) is None  # taken over
    # ...and the takeover refreshed the reservation, so the NEXT duplicate is blocked again.
    with pytest.raises(HTTPException) as e:
        idem.reserve_key(db, **_kw(world))
    assert e.value.status_code == 409


def test_recent_reservation_is_not_taken_over(db, world):
    idem.reserve_key(db, **_kw(world))
    _backdate(db, 5)
    with pytest.raises(HTTPException) as e:
        idem.reserve_key(db, **_kw(world))
    assert e.value.status_code == 409


def test_stale_takeover_still_checks_request_body(db, world):
    idem.reserve_key(db, **_kw(world))
    _backdate(db, idem.STALE_RESERVATION.total_seconds() + 30)
    with pytest.raises(HTTPException) as e:
        idem.reserve_key(db, **_kw(world, body={"a": 999}))
    assert e.value.status_code == 422


def test_natural_key_is_deterministic():
    assert idem.natural_key("a", 1) == idem.natural_key("a", 1)
    assert idem.natural_key("a", 1) != idem.natural_key("a", 2)

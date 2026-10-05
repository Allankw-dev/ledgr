"""Queue throughput and priority: a big broadcast must not make a payment confirmation wait."""

import threading
import time

from sqlalchemy import select, text

from app.core import jobs
from app.core.config import settings
from app.models.job import Job
from tests.conftest import needs_db

pytestmark = needs_db

active = {"now": 0, "max": 0}
guard = threading.Lock()
order: list[str] = []


@jobs.job_handler("test.slow")
def _slow(payload):
    with guard:
        active["now"] += 1
        active["max"] = max(active["max"], active["now"])
    time.sleep(payload.get("sleep", 0.2))  # stands in for waiting on the SMS provider
    with guard:
        active["now"] -= 1
        order.append(payload["name"])


def _enqueue(db, w, name, **kw):
    jobs.enqueue(db, school_id=w.school.id, kind="test.slow", payload={"name": name, "sleep": kw.pop("sleep", 0.2)}, **kw)


def _drain(done_count, timeout=20.0):
    """Run a real worker until `done_count` jobs have finished (or the timeout), then stop it.
    Waiting for a condition instead of sleeping a fixed time keeps these stable on a slow machine."""
    from app.core.database import SystemSessionLocal

    stop = threading.Event()
    t = threading.Thread(target=jobs.worker_loop, args=(stop, 0.05), daemon=True)
    t.start()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with SystemSessionLocal() as s:
            if s.execute(text("SELECT count(*) FROM jobs WHERE status='done'")).scalar_one() >= done_count:
                break
        time.sleep(0.05)
    stop.set()
    t.join(timeout=10)


def test_jobs_run_concurrently_not_one_after_another(db, world, monkeypatch):
    monkeypatch.setattr(settings, "job_concurrency", 8)
    active.update(now=0, max=0)
    order.clear()
    for i in range(32):
        _enqueue(db, world, f"j{i}")
    db.commit()

    started = time.monotonic()
    _drain(32)
    elapsed_for_32 = time.monotonic() - started

    done = db.execute(text("SELECT count(*) FROM jobs WHERE status='done'")).scalar_one()
    assert done == 32, f"only {done} of 32 finished"
    assert active["max"] >= 4  # really ran side by side
    # one at a time this would take 32 x 0.2 = 6.4 s; 8 at a time is ~0.8 s
    assert elapsed_for_32 < 5.0


def test_concurrency_of_one_still_works(db, world, monkeypatch):
    monkeypatch.setattr(settings, "job_concurrency", 1)
    active.update(now=0, max=0)
    for i in range(3):
        _enqueue(db, world, f"s{i}", sleep=0.05)
    db.commit()
    _drain(3)
    assert db.execute(text("SELECT count(*) FROM jobs WHERE status='done'")).scalar_one() == 3
    assert active["max"] == 1


def test_urgent_job_jumps_a_long_queue(db, world, monkeypatch):
    monkeypatch.setattr(settings, "job_concurrency", 2)
    order.clear()
    for i in range(20):
        _enqueue(db, world, f"bulk{i}", sleep=0.05)  # the broadcast, queued first
    _enqueue(db, world, "PAYMENT", sleep=0.05, urgent=True)  # queued LAST
    db.commit()
    _drain(21)
    assert order.index("PAYMENT") < 4, order  # first in line, not 21st


def test_a_crashing_job_does_not_stop_the_others(db, world, monkeypatch):
    @jobs.job_handler("test.boom")
    def _boom(payload):
        raise RuntimeError("provider down")

    monkeypatch.setattr(settings, "job_concurrency", 4)
    order.clear()
    jobs.enqueue(db, school_id=world.school.id, kind="test.boom", payload={})
    for i in range(3):
        _enqueue(db, world, f"ok{i}", sleep=0.05)
    db.commit()
    _drain(3)
    assert sorted(order) == ["ok0", "ok1", "ok2"]
    boom = db.execute(select(Job).where(Job.kind == "test.boom")).scalar_one()
    assert boom.status == "pending" and boom.attempts == 1 and "provider down" in boom.last_error  # retried later


def test_payment_notifications_are_marked_urgent(db, world):
    from decimal import Decimal
    from app.models.enums import PaymentMethod
    from app.services import payment_service as ps
    from datetime import datetime, timezone

    ps.record_confirmed_payment(db, world.school.id, world.student.id, Decimal("1000"), PaymentMethod.CASH, invoice_id=world.invoice.id)
    job = db.execute(select(Job).where(Job.kind == "notify_payment_result")).scalar_one()
    assert job.run_at < datetime.now(timezone.utc) - jobs.URGENT_HEAD_START / 2


# --- enqueue_many: one statement for many jobs ---------------------------------


def test_enqueue_many_inserts_all_and_reports_only_the_new_ones(db, world):
    rows = [{"school_id": world.school.id, "kind": "test.slow", "payload": {"name": f"m{i}"}, "dedupe_key": f"bulk:{i}"} for i in range(5)]
    assert jobs.enqueue_many(db, rows) == {f"bulk:{i}" for i in range(5)}
    db.commit()
    again = rows + [{"school_id": world.school.id, "kind": "test.slow", "payload": {"name": "new"}, "dedupe_key": "bulk:new"}]
    assert jobs.enqueue_many(db, again) == {"bulk:new"}  # the five existing ones were skipped, not duplicated
    db.commit()
    assert db.execute(text("SELECT count(*) FROM jobs")).scalar_one() == 6
    assert jobs.enqueue_many(db, []) == set()


def test_enqueue_many_urgent_rows_jump_the_queue(db, world, monkeypatch):
    monkeypatch.setattr(settings, "job_concurrency", 2)
    order.clear()
    normal = [{"school_id": world.school.id, "kind": "test.slow", "payload": {"name": f"n{i}", "sleep": 0.05}, "dedupe_key": f"n:{i}"} for i in range(20)]
    rush = [{"school_id": world.school.id, "kind": "test.slow", "payload": {"name": "RUSH", "sleep": 0.05}, "dedupe_key": "r:1", "urgent": True}]
    jobs.enqueue_many(db, normal + rush)
    db.commit()
    _drain(21)
    assert order.index("RUSH") < 4, order

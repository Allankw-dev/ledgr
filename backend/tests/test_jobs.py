from sqlalchemy import select, text

from app.core import jobs
from app.models.job import Job
from tests.conftest import needs_db

pytestmark = needs_db

seen = []


@jobs.job_handler("test.ok")
def _ok(payload):
    seen.append(payload["n"])


@jobs.job_handler("test.boom")
def _boom(payload):
    raise RuntimeError("provider down")


def _enqueue(db, w, kind="test.ok", **kw):
    ok = jobs.enqueue(db, school_id=w.school.id, kind=kind, payload=kw.pop("payload", {"n": 1}), **kw)
    db.commit()
    return ok


def _job(db):
    db.expire_all()
    return db.execute(select(Job)).scalar_one()


def test_dedupe_key_blocks_second_enqueue(db, world):
    assert _enqueue(db, world, dedupe_key="same") is True
    assert _enqueue(db, world, dedupe_key="same") is False
    assert len(db.execute(select(Job)).scalars().all()) == 1


def test_claim_runs_handler_and_marks_done(db, world):
    seen.clear()
    _enqueue(db, world, payload={"n": 42})
    [job] = jobs.claim_jobs(10)
    assert job["attempts"] == 1
    jobs.run_one(job)
    assert seen == [42] and _job(db).status == "done"


def test_two_workers_never_claim_the_same_job(db, world):
    for i in range(6):
        _enqueue(db, world, payload={"n": i})
    a = jobs.claim_jobs(4)
    b = jobs.claim_jobs(4)
    ids = [j["id"] for j in a + b]
    assert len(ids) == len(set(ids)) == 6


def test_failure_is_retried_with_backoff_then_goes_dead(db, world):
    _enqueue(db, world, kind="test.boom", max_attempts=2)
    [job] = jobs.claim_jobs(10)
    jobs.run_one(job)
    j = _job(db)
    assert j.status == "pending" and j.attempts == 1 and "provider down" in j.last_error
    assert jobs.claim_jobs(10) == []  # not due yet — backed off

    db.execute(text("UPDATE jobs SET run_at = now() - interval '1 second'"))
    db.commit()
    [job] = jobs.claim_jobs(10)
    jobs.run_one(job)
    assert _job(db).status == "dead"  # kept for inspection, never silently dropped


def test_job_from_a_crashed_worker_is_reclaimed_after_visibility_timeout(db, world):
    _enqueue(db, world)
    assert len(jobs.claim_jobs(10)) == 1
    assert jobs.claim_jobs(10) == []  # still running, not yet stale
    db.execute(text("UPDATE jobs SET locked_at = now() - interval '1 hour'"))
    db.commit()
    assert len(jobs.claim_jobs(10)) == 1


def test_unknown_kind_does_not_loop_forever(db, world):
    _enqueue(db, world, kind="from.the.future")
    [job] = jobs.claim_jobs(10)
    jobs.run_one(job)
    assert _job(db).status == "dead"


def test_backoff_grows_and_is_capped():
    lo, hi = jobs._backoff_seconds(1), jobs._backoff_seconds(2)
    assert 24 <= lo <= 36 and 48 <= hi <= 72
    assert jobs._backoff_seconds(30) <= 3600 * 1.2

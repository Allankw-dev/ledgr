"""Durable background job queue on Postgres.

Why not just the in-process thread pool (core/background.py)? Work queued
there lives in one process's memory: a crash, deploy or worker recycle
silently drops it, and a failure is logged and forgotten. Here a job is a row:

  * enqueue(db, ...) joins the CALLER'S transaction (transactional outbox) —
    "payment confirmed" and "text the parent" commit together or not at all.
  * Workers claim rows with FOR UPDATE SKIP LOCKED, so any number of worker
    processes/instances can run side by side without double-processing.
  * A failed job is retried with exponential backoff + jitter, then parked as
    'dead' (kept for inspection, never silently lost).
  * A job whose worker died mid-run (status 'running' past the visibility
    timeout) is handed to another worker.
  * dedupe_key makes enqueueing idempotent (a retried request can't fan out twice).

Delivery is at-least-once: a handler must be safe to run twice. (Handlers here
send a notification — the worst case is a duplicate text, never a lost one.)
"""

from __future__ import annotations

import logging
import os
import random
import socket
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SystemSessionLocal
from app.models.job import Job

logger = logging.getLogger(__name__)

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"

_handlers: dict[str, Callable[[dict[str, Any]], None]] = {}


def job_handler(kind: str):
    """Register a function as the handler for a job kind."""

    def deco(fn: Callable[[dict[str, Any]], None]):
        _handlers[kind] = fn
        return fn

    return deco


def enqueue(
    db: Session,
    *,
    school_id: str,
    kind: str,
    payload: dict[str, Any],
    dedupe_key: str | None = None,
    delay_seconds: int = 0,
    max_attempts: int | None = None,
) -> bool:
    """Add a job inside the caller's transaction (does NOT commit). Returns
    False if a job with this dedupe_key already exists."""
    values: dict[str, Any] = {
        "school_id": school_id,
        "kind": kind,
        "payload": payload,
        "dedupe_key": dedupe_key,
        "max_attempts": max_attempts or settings.job_max_attempts,
    }
    values["id"] = str(uuid.uuid4())
    if delay_seconds:
        values["run_at"] = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
    stmt = pg_insert(Job).values(**values)
    if dedupe_key:
        stmt = stmt.on_conflict_do_nothing(index_elements=["dedupe_key"], index_where=text("dedupe_key IS NOT NULL"))
    result = db.execute(stmt)
    return result.rowcount == 1


# --- claiming / finishing -----------------------------------------------------

_CLAIM_SQL = text(
    """
    UPDATE jobs SET status = 'running', locked_at = now(), locked_by = :worker, attempts = attempts + 1
    WHERE id IN (
        SELECT id FROM jobs
        WHERE (status = 'pending' AND run_at <= now())
           OR (status = 'running' AND locked_at < now() - make_interval(secs => :visibility))
        ORDER BY run_at
        FOR UPDATE SKIP LOCKED
        LIMIT :n
    )
    RETURNING id, kind, payload, attempts, max_attempts
    """
)


def claim_jobs(limit: int = 10) -> list[dict[str, Any]]:
    with SystemSessionLocal() as db:
        rows = db.execute(
            _CLAIM_SQL,
            {"worker": WORKER_ID, "n": limit, "visibility": settings.job_visibility_timeout_seconds},
        ).mappings().all()
        db.commit()
        return [dict(r) for r in rows]


def _backoff_seconds(attempts: int) -> float:
    # 30s, 60s, 120s, 240s ... capped at 1h, +/-20% jitter so retries don't stampede.
    base = min(30 * (2 ** (attempts - 1)), 3600)
    return base * random.uniform(0.8, 1.2)


def _finish(job_id: str, ok: bool, attempts: int, max_attempts: int, error: str | None) -> None:
    with SystemSessionLocal() as db:
        if ok:
            db.execute(
                text("UPDATE jobs SET status='done', finished_at=now(), locked_at=NULL, last_error=NULL WHERE id=:id"),
                {"id": job_id},
            )
        elif attempts >= max_attempts:
            db.execute(
                text("UPDATE jobs SET status='dead', finished_at=now(), locked_at=NULL, last_error=:e WHERE id=:id"),
                {"id": job_id, "e": (error or "")[:2000]},
            )
        else:
            db.execute(
                text(
                    "UPDATE jobs SET status='pending', locked_at=NULL, last_error=:e, "
                    "run_at = now() + make_interval(secs => :delay) WHERE id=:id"
                ),
                {"id": job_id, "e": (error or "")[:2000], "delay": _backoff_seconds(attempts)},
            )
        db.commit()


def run_one(job: dict[str, Any]) -> None:
    handler = _handlers.get(job["kind"])
    if handler is None:
        # A worker that doesn't know this kind (older deploy) must not burn its attempts.
        logger.error("No handler registered for job kind %r", job["kind"])
        _finish(job["id"], False, job["max_attempts"], job["max_attempts"], f"no handler for {job['kind']}")
        return
    try:
        handler(job["payload"])
    except Exception as exc:  # noqa: BLE001 — any handler failure => retry/backoff
        logger.warning("Job %s (%s) failed on attempt %s: %s", job["id"], job["kind"], job["attempts"], exc)
        _finish(job["id"], False, job["attempts"], job["max_attempts"], f"{type(exc).__name__}: {exc}")
    else:
        _finish(job["id"], True, job["attempts"], job["max_attempts"], None)


def purge_finished(older_than_days: int = 7) -> None:
    with SystemSessionLocal() as db:
        db.execute(
            text("DELETE FROM jobs WHERE status = 'done' AND finished_at < now() - make_interval(days => :d)"),
            {"d": older_than_days},
        )
        db.execute(text("DELETE FROM idempotency_keys WHERE expires_at < now()"))
        db.execute(text("DELETE FROM refresh_tokens WHERE expires_at < now() - interval '7 days'"))
        db.commit()


# --- the worker loop ------------------------------------------------------------


def worker_loop(stop: threading.Event, poll_seconds: float | None = None) -> None:
    """Claim and run jobs until `stop` is set. Sleeps only when idle."""
    from app.services import job_handlers  # noqa: F401 — registers the handlers

    poll = poll_seconds if poll_seconds is not None else settings.job_poll_seconds
    last_maintenance = 0.0
    logger.info("Job worker %s started", WORKER_ID)
    while not stop.is_set():
        try:
            jobs = claim_jobs(settings.job_batch_size)
        except Exception:  # noqa: BLE001 — DB blip: back off, don't die
            logger.exception("Could not claim jobs")
            stop.wait(5)
            continue
        for job in jobs:
            run_one(job)
        if time.monotonic() - last_maintenance > 3600:
            last_maintenance = time.monotonic()
            try:
                purge_finished()
            except Exception:  # noqa: BLE001
                logger.exception("Queue maintenance failed")
        if not jobs:
            stop.wait(poll)
    logger.info("Job worker %s stopped", WORKER_ID)

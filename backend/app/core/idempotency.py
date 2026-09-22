"""Idempotency keys for state-changing endpoints.

A client (or a flaky mobile connection, or an impatient double click) may send
the same request twice. With an `Idempotency-Key` header the second call gets
the FIRST call's stored response instead of doing the work again.

How it stays correct under concurrency: the key row is inserted in the SAME
transaction as the business change. Postgres' unique index makes a concurrent
duplicate wait for the first transaction to finish; when it commits, the
duplicate sees the stored response and replays it. If the first one fails and
rolls back, the key never existed and the retry runs normally. There is no
"in progress" limbo state to get stuck in.

Usage in a route:

    return run_idempotent(
        db, school_id=school_id, user_id=user.user_id, scope="payments.record",
        key=idempotency_key, request_body=data.model_dump(mode="json"),
        action=lambda: (201, PaymentResponse.model_validate(pay(db, ..., commit=False)).model_dump(mode="json")),
    )

`action` must NOT commit; it returns (status_code, json_body). Without a key
the action just runs and commits (behaviour unchanged for old clients).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.idempotency import IdempotencyKey

DEFAULT_TTL = timedelta(hours=24)
MAX_KEY_LENGTH = 200


def _hash(body: Any) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def natural_key(*parts: Any) -> str:
    """A deterministic key for endpoints where identical content should be treated
    as the same request (e.g. the same announcement text sent twice)."""
    return "auto:" + _hash(list(parts))[:40]


def run_idempotent(
    db: Session,
    *,
    school_id: str,
    user_id: str,
    scope: str,
    key: str | None,
    request_body: Any,
    action: Callable[[], tuple[int, Any]],
    ttl: timedelta = DEFAULT_TTL,
    on_commit: Callable[[], None] | None = None,
):
    """`on_commit`, if given, runs immediately after a SUCCESSFUL commit of a
    freshly-run action (never on a replay — nothing changed on a replay, so
    there's nothing to invalidate). For cache invalidation: cache.bump() isn't
    part of the SQL transaction, so it has to happen after commit, not before —
    calling it before commit could unblock a reader into re-caching data from
    a transaction that hasn't landed yet."""
    if not key:
        status_code, body = action()
        db.commit()
        if on_commit:
            on_commit()
        return JSONResponse(status_code=status_code, content=body)

    key = key.strip()
    if not key or len(key) > MAX_KEY_LENGTH:
        raise HTTPException(422, f"Idempotency-Key must be 1-{MAX_KEY_LENGTH} characters")

    request_hash = _hash(request_body)
    inserted = db.execute(
        pg_insert(IdempotencyKey)
        .values(
            school_id=school_id,
            user_id=user_id,
            scope=scope,
            key=key,
            request_hash=request_hash,
            expires_at=datetime.now(timezone.utc) + ttl,
        )
        .on_conflict_do_nothing(constraint="uq_idempotency_key")
        .returning(IdempotencyKey.id)
    ).scalar_one_or_none()

    if inserted is None:
        # Someone (an earlier request, or one that just committed) already used this key.
        db.rollback()
        existing = db.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.school_id == school_id,
                IdempotencyKey.user_id == user_id,
                IdempotencyKey.scope == scope,
                IdempotencyKey.key == key,
            )
        ).scalar_one_or_none()
        if existing is None or existing.response is None:
            raise HTTPException(409, "A request with this Idempotency-Key is still being processed. Retry shortly.")
        if existing.request_hash != request_hash:
            raise HTTPException(422, "This Idempotency-Key was already used with a different request.")
        return JSONResponse(
            status_code=existing.status_code or 200,
            content=existing.response,
            headers={"Idempotent-Replay": "true"},
        )

    try:
        status_code, body = action()
        db.execute(
            IdempotencyKey.__table__.update()
            .where(IdempotencyKey.id == inserted)
            .values(status_code=status_code, response=body)
        )
        db.commit()  # business change + stored response land atomically
    except BaseException:
        db.rollback()  # the key row goes with it, so a retry can run
        raise
    if on_commit:
        on_commit()
    return JSONResponse(status_code=status_code, content=body)


def reserve_key(
    db: Session,
    *,
    school_id: str,
    user_id: str,
    scope: str,
    key: str,
    request_body: Any,
) -> tuple[str, Any] | None:
    """Lower-level half of run_idempotent, for endpoints whose action includes
    a non-transactional external call (e.g. calling a payment provider) that
    can't sit inside a single DB transaction the way run_idempotent expects.

    Reserves the key row and COMMITS immediately (so the reservation is
    visible to a concurrent duplicate request right away), then returns None —
    caller should do its external work and then call store_result(). If the
    key already has a stored response, returns ("replay", response) instead —
    caller should return that response as-is without repeating the external call.
    Raises HTTPException(409) if another request is still mid-flight, or
    HTTPException(422) if the same key was used for a different request body.
    """
    key = (key or "").strip()
    if not key or len(key) > MAX_KEY_LENGTH:
        raise HTTPException(422, f"Idempotency-Key must be 1-{MAX_KEY_LENGTH} characters")
    request_hash = _hash(request_body)

    inserted = db.execute(
        pg_insert(IdempotencyKey)
        .values(
            school_id=school_id,
            user_id=user_id,
            scope=scope,
            key=key,
            request_hash=request_hash,
            expires_at=datetime.now(timezone.utc) + DEFAULT_TTL,
        )
        .on_conflict_do_nothing(constraint="uq_idempotency_key")
        .returning(IdempotencyKey.id)
    ).scalar_one_or_none()
    db.commit()

    if inserted is not None:
        return None  # fresh reservation — caller does the work

    existing = db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.school_id == school_id,
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.scope == scope,
            IdempotencyKey.key == key,
        )
    ).scalar_one_or_none()
    if existing is None or existing.response is None:
        raise HTTPException(409, "A request with this Idempotency-Key is still being processed. Retry shortly.")
    if existing.request_hash != request_hash:
        raise HTTPException(422, "This Idempotency-Key was already used with a different request.")
    return "replay", existing.response


def store_result(
    db: Session, *, school_id: str, user_id: str, scope: str, key: str, status_code: int, response: Any
) -> None:
    """Second half of the reserve/store pair — call after the external work
    and the DB write both succeeded. Commits."""
    db.execute(
        IdempotencyKey.__table__.update()
        .where(
            IdempotencyKey.school_id == school_id,
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.scope == scope,
            IdempotencyKey.key == key.strip(),
        )
        .values(status_code=status_code, response=response)
    )
    db.commit()


def release_key(db: Session, *, school_id: str, user_id: str, scope: str, key: str) -> None:
    """Call if the external work FAILED after reserve_key succeeded, so a
    retry with the same key can try again instead of getting stuck at 409
    forever. Deletes the reservation."""
    db.execute(
        IdempotencyKey.__table__.delete().where(
            IdempotencyKey.school_id == school_id,
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.scope == scope,
            IdempotencyKey.key == key.strip(),
        )
    )
    db.commit()

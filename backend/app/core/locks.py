"""Cross-process locks backed by Postgres advisory locks.

Used so that work which must only run once at a time (the overdue-reminder
sweep, in particular) is safe even when the API runs as several worker
processes or several instances.

Transaction-level advisory locks (pg_try_advisory_xact_lock) are used on a
dedicated connection that stays inside one open transaction for the lifetime
of the `with` block. That is safe with connection poolers in transaction mode
(the connection is pinned while the transaction is open) and the lock is
released automatically if the process dies or the connection drops.
"""

import hashlib
import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import text

from app.core.database import system_engine

logger = logging.getLogger(__name__)


def _lock_key(name: str) -> int:
    # Stable signed 64-bit key derived from the lock name.
    return int.from_bytes(hashlib.blake2b(name.encode(), digest_size=8).digest(), "big", signed=True)


@contextmanager
def try_advisory_lock(name: str) -> Iterator[bool]:
    """Yields True if this caller now holds the named lock, False if another
    process already does. Never blocks.

        with try_advisory_lock("overdue-sweep:school-123") as got:
            if not got:
                return  # someone else is already doing this
            ...
    """
    conn = system_engine.connect()
    try:
        got = bool(
            conn.execute(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": _lock_key(name)}).scalar()
        )
        yield got
    finally:
        try:
            conn.rollback()  # ends the transaction, releasing the lock
        finally:
            conn.close()

from datetime import datetime
from typing import Any

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Index, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.school import gen_uuid


class Job(Base):
    """A unit of background work in the durable queue (see core/jobs.py).

    Lives in Postgres rather than in process memory, so a job survives a
    crash or deploy, is retried with backoff, and can be picked up by any
    worker (claimed with FOR UPDATE SKIP LOCKED). Enqueuing happens inside
    the caller's own transaction — a payment and its "notify the parent"
    job commit together or not at all (the transactional-outbox pattern).
    """

    __tablename__ = "jobs"
    __table_args__ = (
        # The claim query scans only what is actually waiting.
        Index("ix_jobs_pending_run_at", "run_at", postgresql_where=text("status = 'pending'")),
        Index("ix_jobs_running_locked_at", "locked_at", postgresql_where=text("status = 'running'")),
        # Same dedupe_key can't be enqueued twice (idempotent fan-out).
        Index("ux_jobs_dedupe_key", "dedupe_key", unique=True, postgresql_where=text("dedupe_key IS NOT NULL")),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default="5")
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

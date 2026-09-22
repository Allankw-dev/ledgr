"""integrity constraints, hot-path indexes, durable job queue, idempotency keys

Revision ID: d3a7e1c5f9b2
Revises: c8d2f4a6b1e3
Create Date: 2026-09-21 00:00:00.000000

1. DB-level guarantees for things the app only checked in Python (a
   check-then-insert is a race; a unique index is not):
     * one invoice per (student, term)
     * a provider transaction id (Daraja CheckoutRequestID / C2B TransID)
       maps to at most one payment
   If existing data already violates one, the migration STOPS with a clear
   message instead of deleting anyone's financial records.
2. Indexes for queries that had none: the covering index used to total an
   invoice's confirmed payments, and users(school_id, role).
3. `jobs` (durable queue, SKIP LOCKED) and `idempotency_keys` tables, both
   tenant-isolated with the same RLS pattern as every other school table.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d3a7e1c5f9b2"
down_revision = "c8d2f4a6b1e3"
branch_labels = None
depends_on = None


def _fail_if_duplicates(sql: str, what: str) -> None:
    rows = op.get_bind().execute(sa.text(sql)).fetchall()
    if rows:
        raise RuntimeError(
            f"Cannot add the unique guarantee for {what}: {len(rows)} duplicate group(s) already exist "
            f"(first: {tuple(rows[0])}). Resolve them by hand (void / reverse the extras), then re-run "
            f"`alembic upgrade head`. Nothing was changed."
        )


def upgrade() -> None:
    # ---- 1. integrity ------------------------------------------------------
    _fail_if_duplicates(
        "SELECT student_id, term_id, count(*) FROM invoices GROUP BY 1, 2 HAVING count(*) > 1",
        "one invoice per student per term",
    )
    _fail_if_duplicates(
        "SELECT external_txn_id, count(*) FROM payments WHERE external_txn_id IS NOT NULL "
        "GROUP BY 1 HAVING count(*) > 1",
        "one payment per provider transaction id",
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_invoices_student_term ON invoices (student_id, term_id)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_payments_external_txn_id ON payments (external_txn_id) "
        "WHERE external_txn_id IS NOT NULL"
    )

    # ---- 2. indexes --------------------------------------------------------
    # Totalling an invoice = WHERE invoice_id = ? AND status = 'CONFIRMED' -> SUM(amount).
    # INCLUDE (amount) makes it an index-only scan (no table lookups).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_payments_invoice_status ON payments (invoice_id, status) INCLUDE (amount)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_school_role ON users (school_id, role)")

    # ---- 3. queue + idempotency -------------------------------------------
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("school_id", sa.String(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("dedupe_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_school_id", "jobs", ["school_id"])
    op.execute("CREATE INDEX ix_jobs_pending_run_at ON jobs (run_at) WHERE status = 'pending'")
    op.execute("CREATE INDEX ix_jobs_running_locked_at ON jobs (locked_at) WHERE status = 'running'")
    op.execute("CREATE UNIQUE INDEX ux_jobs_dedupe_key ON jobs (dedupe_key) WHERE dedupe_key IS NOT NULL")

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("school_id", sa.String(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("school_id", "user_id", "scope", "key", name="uq_idempotency_key"),
    )
    op.create_index("ix_idempotency_keys_school_id", "idempotency_keys", ["school_id"])
    op.create_index("ix_idempotency_keys_expires_at", "idempotency_keys", ["expires_at"])

    for table in ("jobs", "idempotency_keys"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            DO $$
            BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ledgr_app') THEN
                DROP POLICY IF EXISTS tenant_isolation ON {table};
                CREATE POLICY tenant_isolation ON {table} FOR ALL TO ledgr_app
                  USING (school_id = (select current_setting('app.current_school_id', true))::text)
                  WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);
              END IF;
            END
            $$;
            """
        )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_table("jobs")
    op.execute("DROP INDEX IF EXISTS ix_users_school_role")
    op.execute("DROP INDEX IF EXISTS ix_payments_invoice_status")
    op.execute("DROP INDEX IF EXISTS ux_payments_external_txn_id")
    op.execute("DROP INDEX IF EXISTS ux_invoices_student_term")

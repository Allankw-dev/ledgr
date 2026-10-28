"""job priority column

Revision ID: e1b3c5d7f9a2
Revises: d4a7c9e2b815

Replaces the "urgent jobs get a run_at one day in the past" trick with a real `priority` column. Workers
now claim ORDER BY priority DESC, run_at. Additive: existing rows get priority 0 (normal), and old code that
doesn't know about the column keeps working because it has a server default.
"""

from alembic import op
import sqlalchemy as sa

revision = "e1b3c5d7f9a2"
down_revision = "d4a7c9e2b815"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("priority", sa.Integer(), nullable=False, server_default="0"))
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_jobs_pending_priority_run_at ON jobs (priority DESC, run_at) "
        "WHERE status = 'pending'"
    )
    op.execute("DROP INDEX IF EXISTS ix_jobs_pending_run_at")


def downgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_pending_run_at ON jobs (run_at) WHERE status = 'pending'")
    op.execute("DROP INDEX IF EXISTS ix_jobs_pending_priority_run_at")
    op.drop_column("jobs", "priority")

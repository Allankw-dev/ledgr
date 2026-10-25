"""add school subscription

Revision ID: d4a7c9e2b815
Revises: c1f8a3e6b4d2
Create Date: 2026-10-11 09:00:00.000000

Additive only. Every existing school becomes ACTIVE with no expiry date, so nothing changes for a
school until the platform operator sets a trial or a paid-until date.
"""

from alembic import op
import sqlalchemy as sa

revision = "d4a7c9e2b815"
down_revision = "c1f8a3e6b4d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schools", sa.Column("plan", sa.String(), nullable=False, server_default="STANDARD"))
    op.add_column("schools", sa.Column("subscription_status", sa.String(), nullable=False, server_default="ACTIVE"))
    op.add_column("schools", sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("schools", sa.Column("paid_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("schools", sa.Column("learner_limit", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("schools", "learner_limit")
    op.drop_column("schools", "paid_until")
    op.drop_column("schools", "trial_ends_at")
    op.drop_column("schools", "subscription_status")
    op.drop_column("schools", "plan")

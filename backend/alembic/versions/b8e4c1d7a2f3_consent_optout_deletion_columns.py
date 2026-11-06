"""Consent record, email opt-out and account-deletion marker on users

Revision ID: b8e4c1d7a2f3
Revises: 6dedb9109fcc
Create Date: 2026-11-05 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b8e4c1d7a2f3'
down_revision = '6dedb9109fcc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # "IF NOT EXISTS" on purpose: these columns were first added to production by hand to bring login back after the
    # code was deployed ahead of this migration, so running it again must not fail.
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_version VARCHAR")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_opt_out BOOLEAN NOT NULL DEFAULT false")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_opt_out_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE")


def downgrade() -> None:
    op.drop_column('users', 'deleted_at')
    op.drop_column('users', 'email_opt_out_at')
    op.drop_column('users', 'email_opt_out')
    op.drop_column('users', 'terms_version')
    op.drop_column('users', 'terms_accepted_at')

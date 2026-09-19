"""add users.token_version (server-side session revocation)

Revision ID: c4a8e2b6d0f3
Revises: b7e3d9f1c2a5
Create Date: 2026-09-19 00:00:00.000000

Every JWT now carries the user's token_version. Bumping it (password reset)
invalidates all tokens issued earlier. Existing tokens carry no version and
are treated as version 0, so nobody is logged out by this migration itself.
"""

from alembic import op

revision = "c4a8e2b6d0f3"
down_revision = "b7e3d9f1c2a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS token_version")

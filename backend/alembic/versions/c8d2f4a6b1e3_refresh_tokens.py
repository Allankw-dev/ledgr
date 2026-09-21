"""refresh tokens (rotating, hashed, family-tracked)

Revision ID: c8d2f4a6b1e3
Revises: a8f3c1d6e2b9
Create Date: 2026-09-21 00:00:00.000000

Access tokens become short-lived (15 min by default); a refresh token, stored
here only as a SHA-256 hash, quietly gets a new one. RLS is enabled with no
policy, so the restricted ledgr_app role can't read or write this table at all
— only the owner connection used by the auth endpoints (get_system_db) can.
"""

import sqlalchemy as sa
from alembic import op

revision = "c8d2f4a6b1e3"
down_revision = "a8f3c1d6e2b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("family_id", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])
    op.execute("ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("refresh_tokens")

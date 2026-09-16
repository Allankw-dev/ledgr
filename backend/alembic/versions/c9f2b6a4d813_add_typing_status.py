"""add typing_status table for WhatsApp-style typing indicator

Revision ID: c9f2b6a4d813
Revises: b3e6a1f8c4d7
Create Date: 2026-09-16 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "c9f2b6a4d813"
down_revision = "b3e6a1f8c4d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "typing_status",
        sa.Column("school_id", sa.String(), sa.ForeignKey("schools.id"), primary_key=True),
        sa.Column("parent_user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("parent_typing_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("staff_typing_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("typing_status")

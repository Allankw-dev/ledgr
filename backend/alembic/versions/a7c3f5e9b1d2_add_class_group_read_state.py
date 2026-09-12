"""add class group read state for unread-count notifications

Revision ID: a7c3f5e9b1d2
Revises: f2a8c91d4e6b
Create Date: 2026-09-12 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "a7c3f5e9b1d2"
down_revision = "f2a8c91d4e6b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "class_group_read_state",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("class_id", sa.String(), sa.ForeignKey("school_classes.id"), nullable=False),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "class_id", name="uq_class_group_read_state"),
    )
    op.create_index("ix_class_group_read_state_user", "class_group_read_state", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_class_group_read_state_user", table_name="class_group_read_state")
    op.drop_table("class_group_read_state")

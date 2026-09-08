"""add messages table for parent-school messaging

Revision ID: b7e91a3c5f42
Revises: a1c4f2e8b7d3
Create Date: 2026-09-08 10:30:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "b7e91a3c5f42"
down_revision = "a1c4f2e8b7d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    message_sender_role = sa.Enum("PARENT", "STAFF", name="messagesenderrole")
    message_sender_role.create(op.get_bind(), checkfirst=True)

    sender_role_column_type = sa.Enum("PARENT", "STAFF", name="messagesenderrole", create_type=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("school_id", sa.String(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("parent_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("student_id", sa.String(), sa.ForeignKey("students.id"), nullable=True),
        sa.Column("sender_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sender_role", sender_role_column_type, nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("read_by_parent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_by_staff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_messages_school_id", "messages", ["school_id"])
    op.create_index("ix_messages_parent_user_id", "messages", ["parent_user_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_messages_parent_user_id", table_name="messages")
    op.drop_index("ix_messages_school_id", table_name="messages")
    op.drop_table("messages")

    sa.Enum(name="messagesenderrole").drop(op.get_bind(), checkfirst=True)

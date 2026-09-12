"""add teacher role, class-teacher assignments, and class group chat

Revision ID: f2a8c91d4e6b
Revises: de4222bc0886
Create Date: 2026-09-12 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "f2a8c91d4e6b"
down_revision = "de4222bc0886"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres requires ALTER TYPE ... ADD VALUE to run outside a transaction
    # block. Alembic wraps migrations in a transaction by default, so this
    # has to be explicitly carved out with autocommit_block() — running it
    # inside the normal transaction fails with "ALTER TYPE ... cannot run
    # inside a transaction block" every time, unconditionally.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'TEACHER'")

    op.create_table(
        "teacher_class_assignments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("teacher_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("class_id", sa.String(), sa.ForeignKey("school_classes.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("teacher_user_id", "class_id", name="uq_teacher_class"),
    )
    op.create_index("ix_teacher_class_assignments_teacher", "teacher_class_assignments", ["teacher_user_id"])
    op.create_index("ix_teacher_class_assignments_class", "teacher_class_assignments", ["class_id"])

    op.create_table(
        "class_group_messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("school_id", sa.String(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("class_id", sa.String(), sa.ForeignKey("school_classes.id"), nullable=False),
        sa.Column("sender_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_class_group_messages_class_id", "class_group_messages", ["class_id"])
    op.create_index("ix_class_group_messages_created_at", "class_group_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_class_group_messages_created_at", table_name="class_group_messages")
    op.drop_index("ix_class_group_messages_class_id", table_name="class_group_messages")
    op.drop_table("class_group_messages")

    op.drop_index("ix_teacher_class_assignments_class", table_name="teacher_class_assignments")
    op.drop_index("ix_teacher_class_assignments_teacher", table_name="teacher_class_assignments")
    op.drop_table("teacher_class_assignments")

    # Postgres has no ALTER TYPE ... DROP VALUE — removing an enum value
    # cleanly requires rebuilding the type. Left as a no-op: downgrading
    # this migration won't un-ring that bell, which is normal/expected for
    # additive enum changes and matches how most teams handle this.

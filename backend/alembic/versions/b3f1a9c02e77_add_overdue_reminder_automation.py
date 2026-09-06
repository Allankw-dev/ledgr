"""add overdue reminder automation

Revision ID: b3f1a9c02e77
Revises: 90b11f4d1d34
Create Date: 2026-09-05 21:45:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "b3f1a9c02e77"
down_revision = "90b11f4d1d34"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "schools",
        sa.Column("auto_reminders_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
    )

    op.create_table(
        "invoice_reminder_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("invoice_id", sa.String(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("school_id", sa.String(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_invoice_reminder_logs_invoice_id", "invoice_reminder_logs", ["invoice_id"])
    op.create_index("ix_invoice_reminder_logs_school_id", "invoice_reminder_logs", ["school_id"])


def downgrade() -> None:
    op.drop_index("ix_invoice_reminder_logs_school_id", table_name="invoice_reminder_logs")
    op.drop_index("ix_invoice_reminder_logs_invoice_id", table_name="invoice_reminder_logs")
    op.drop_table("invoice_reminder_logs")
    op.drop_column("schools", "auto_reminders_enabled")

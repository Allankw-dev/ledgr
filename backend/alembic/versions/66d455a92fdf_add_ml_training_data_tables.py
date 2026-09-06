"""add ml training-data tables (invoice_risk_snapshots, invoice_outcomes)

Revision ID: 66d455a92fdf
Revises: 90b11f4d1d34
Create Date: 2026-09-05 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "66d455a92fdf"
down_revision = "90b11f4d1d34"
branch_labels = None
depends_on = None

invoice_outcome_label = postgresql.ENUM(
    "PAID_ON_TIME",
    "PAID_LATE",
    "DEFAULTED",
    name="invoiceoutcomelabel",
)


def upgrade() -> None:
    invoice_outcome_label.create(op.get_bind(), checkfirst=True)
    # Without this, op.create_table below tries to CREATE TYPE again for the
    # "outcome" column, since it doesn't know the type above already made it —
    # fails on a real Postgres DB with "type already exists".
    invoice_outcome_label.create_type = False

    op.create_table(
        "invoice_risk_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("invoice_id", sa.String(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("school_id", sa.String(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("history_score", sa.Float(), nullable=False),
        sa.Column("overdue_score", sa.Float(), nullable=False),
        sa.Column("balance_score", sa.Float(), nullable=False),
        sa.Column("reversal_score", sa.Float(), nullable=False),
        sa.Column("total_score", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(), nullable=False),
    )
    op.create_index("ix_invoice_risk_snapshots_invoice_id", "invoice_risk_snapshots", ["invoice_id"])
    op.create_index("ix_invoice_risk_snapshots_school_id", "invoice_risk_snapshots", ["school_id"])

    op.create_table(
        "invoice_outcomes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("invoice_id", sa.String(), sa.ForeignKey("invoices.id"), nullable=False, unique=True),
        sa.Column("school_id", sa.String(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("outcome", invoice_outcome_label, nullable=False),
        sa.Column("days_late", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_invoice_outcomes_invoice_id", "invoice_outcomes", ["invoice_id"], unique=True)
    op.create_index("ix_invoice_outcomes_school_id", "invoice_outcomes", ["school_id"])


def downgrade() -> None:
    op.drop_index("ix_invoice_outcomes_school_id", table_name="invoice_outcomes")
    op.drop_index("ix_invoice_outcomes_invoice_id", table_name="invoice_outcomes")
    op.drop_table("invoice_outcomes")

    op.drop_index("ix_invoice_risk_snapshots_school_id", table_name="invoice_risk_snapshots")
    op.drop_index("ix_invoice_risk_snapshots_invoice_id", table_name="invoice_risk_snapshots")
    op.drop_table("invoice_risk_snapshots")

    invoice_outcome_label.drop(op.get_bind(), checkfirst=True)

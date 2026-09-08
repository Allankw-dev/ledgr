"""add mpesa_transactions table for C2B reconciliation

Revision ID: a1c4f2e8b7d3
Revises: f4d8e1c6a930
Create Date: 2026-09-08 09:15:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "a1c4f2e8b7d3"
down_revision = "f4d8e1c6a930"
branch_labels = None
depends_on = None


def upgrade() -> None:
    mpesa_transaction_status = sa.Enum(
        "UNMATCHED", "MATCHED", "IGNORED", name="mpesatransactionstatus"
    )

    op.create_table(
        "mpesa_transactions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("trans_id", sa.String(), nullable=False),
        sa.Column("trans_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("bill_ref_number", sa.String(), nullable=True),
        sa.Column("msisdn", sa.String(), nullable=True),
        sa.Column("payer_name", sa.String(), nullable=True),
        sa.Column("status", mpesa_transaction_status, nullable=False, server_default="UNMATCHED"),
        sa.Column("school_id", sa.String(), sa.ForeignKey("schools.id"), nullable=True),
        sa.Column("matched_student_id", sa.String(), sa.ForeignKey("students.id"), nullable=True),
        sa.Column("matched_payment_id", sa.String(), sa.ForeignKey("payments.id"), nullable=True),
        sa.Column("resolved_by_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("trans_id", name="uq_mpesa_transactions_trans_id"),
    )
    op.create_index("ix_mpesa_transactions_trans_id", "mpesa_transactions", ["trans_id"])
    op.create_index("ix_mpesa_transactions_status", "mpesa_transactions", ["status"])
    op.create_index("ix_mpesa_transactions_school_id", "mpesa_transactions", ["school_id"])


def downgrade() -> None:
    op.drop_index("ix_mpesa_transactions_school_id", table_name="mpesa_transactions")
    op.drop_index("ix_mpesa_transactions_status", table_name="mpesa_transactions")
    op.drop_index("ix_mpesa_transactions_trans_id", table_name="mpesa_transactions")
    op.drop_table("mpesa_transactions")

    sa.Enum(name="mpesatransactionstatus").drop(op.get_bind(), checkfirst=True)

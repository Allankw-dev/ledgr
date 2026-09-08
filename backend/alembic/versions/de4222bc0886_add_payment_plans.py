"""add payment plans (parent-facing installment schedules)

Revision ID: de4222bc0886
Revises: b7e91a3c5f42
Create Date: 2026-09-09 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "de4222bc0886"
down_revision = "b7e91a3c5f42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    payment_plan_status = sa.Enum("ACTIVE", "COMPLETED", "CANCELLED", name="paymentplanstatus")
    payment_plan_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "payment_plans",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("invoice_id", sa.String(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("student_id", sa.String(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("school_id", sa.String(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("status", payment_plan_status, nullable=False, server_default="ACTIVE"),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("accepted_by_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_payment_plans_invoice_id", "payment_plans", ["invoice_id"])
    op.create_index("ix_payment_plans_student_id", "payment_plans", ["student_id"])
    op.create_index("ix_payment_plans_school_id", "payment_plans", ["school_id"])

    op.create_table(
        "payment_plan_installments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("plan_id", sa.String(), sa.ForeignKey("payment_plans.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_payment_plan_installments_plan_id", "payment_plan_installments", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_plan_installments_plan_id", table_name="payment_plan_installments")
    op.drop_table("payment_plan_installments")

    op.drop_index("ix_payment_plans_school_id", table_name="payment_plans")
    op.drop_index("ix_payment_plans_student_id", table_name="payment_plans")
    op.drop_index("ix_payment_plans_invoice_id", table_name="payment_plans")
    op.drop_table("payment_plans")

    payment_plan_status = sa.Enum("ACTIVE", "COMPLETED", "CANCELLED", name="paymentplanstatus")
    payment_plan_status.drop(op.get_bind(), checkfirst=True)

"""Platform billing ledger (subscription_payments) and an index for per-school payment health

Revision ID: c1e5a9d3b7f2
Revises: a3c7e9b1d5f2
Create Date: 2026-11-07 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c1e5a9d3b7f2'
down_revision = 'a3c7e9b1d5f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'subscription_payments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('school_id', sa.String(), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('method', sa.String(), nullable=False),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('paid_on', sa.DateTime(timezone=True), nullable=False),
        sa.Column('months_added', sa.Integer(), server_default='0', nullable=False),
        sa.Column('note', sa.String(), nullable=True),
        sa.Column('recorded_by_user_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('voided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('voided_by_user_id', sa.String(), nullable=True),
        sa.Column('void_reason', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recorded_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['voided_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_subscription_payments_school_id', 'subscription_payments', ['school_id'])
    op.create_index(
        'ux_subscription_payments_reference',
        'subscription_payments',
        ['school_id', 'reference'],
        unique=True,
        postgresql_where=sa.text('reference IS NOT NULL AND voided_at IS NULL'),
    )
    op.create_index('ix_payments_school_status_created', 'payments', ['school_id', 'status', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_payments_school_status_created', table_name='payments')
    op.drop_index('ux_subscription_payments_reference', table_name='subscription_payments')
    op.drop_index('ix_subscription_payments_school_id', table_name='subscription_payments')
    op.drop_table('subscription_payments')

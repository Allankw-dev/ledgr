"""Consent record, email opt-out and account-deletion marker on users

Revision ID: b8e4c1d7a2f3
Revises: 6dedb9109fcc
Create Date: 2026-11-05 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b8e4c1d7a2f3'
down_revision = '6dedb9109fcc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('terms_accepted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('terms_version', sa.String(), nullable=True))
    op.add_column('users', sa.Column('email_opt_out', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('users', sa.Column('email_opt_out_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'deleted_at')
    op.drop_column('users', 'email_opt_out_at')
    op.drop_column('users', 'email_opt_out')
    op.drop_column('users', 'terms_version')
    op.drop_column('users', 'terms_accepted_at')

"""Add mpesa_mode to schools (already done by a6c9d2e5f8b1; this revision is intentionally a no-op)

Revision ID: 6dedb9109fcc
Revises: a6c9d2e5f8b1
Create Date: 2026-11-04 15:42:35.317065

The first version of this file was raw `alembic revision --autogenerate` output. It added nothing (mpesa_mode
already exists, from a6c9d2e5f8b1) and instead dropped the invoice_outcomes and invoice_risk_snapshots tables and
about 40 indexes and unique guards that Alembic could not see in the models, among them
ux_payments_external_txn_id, uq_users_teacher_phone and the passkey credential_id uniqueness.

The revision id is kept so every database and the migration chain stay valid, but it now does nothing. A database
that ran the old version is repaired by the next revision (c7e1f3a5b9d2).
"""
from alembic import op  # noqa: F401

revision = "6dedb9109fcc"
down_revision = "a6c9d2e5f8b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

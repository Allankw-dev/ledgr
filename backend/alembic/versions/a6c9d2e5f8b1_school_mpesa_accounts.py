"""per-school M-Pesa accounts

Revision ID: a6c9d2e5f8b1
Revises: f3c5e7a9b1d4

Adds:
  * schools.mpesa_mode  OFF | GLOBAL | OWN. New schools default to OFF. The OLDEST existing school is set to
    GLOBAL so it keeps using the server-wide MPESA_* settings exactly as before; any other existing school starts
    with online M-Pesa OFF, because until now it would have been paying into that one paybill, which is the
    thing this change exists to stop.
  * mpesa_transactions.business_shortcode  the paybill a payment was made to (how it is routed to a school).
  * school_mpesa_accounts  each school's own paybill details, credentials stored encrypted. The table is
    owner-only: RLS is on with no policy, and every privilege is revoked from the restricted/API roles.
"""

import sqlalchemy as sa
from alembic import op

revision = "a6c9d2e5f8b1"
down_revision = "f3c5e7a9b1d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schools", sa.Column("mpesa_mode", sa.String(), nullable=False, server_default="OFF"))
    op.execute(
        "UPDATE schools SET mpesa_mode = 'GLOBAL' "
        "WHERE id = (SELECT id FROM schools ORDER BY created_at, id LIMIT 1)"
    )
    op.add_column("mpesa_transactions", sa.Column("business_shortcode", sa.String(), nullable=True))

    op.create_table(
        "school_mpesa_accounts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("school_id", sa.String(), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("environment", sa.String(), nullable=False),
        sa.Column("shortcode", sa.String(), nullable=False),
        sa.Column("consumer_key_enc", sa.Text(), nullable=False),
        sa.Column("consumer_secret_enc", sa.Text(), nullable=False),
        sa.Column("passkey_enc", sa.Text(), nullable=False),
        sa.Column("callback_token_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("c2b_registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("updated_by_user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("school_id", name="uq_school_mpesa_accounts_school"),
    )
    op.create_index("ix_school_mpesa_accounts_school_id", "school_mpesa_accounts", ["school_id"])
    op.create_index("ix_school_mpesa_accounts_shortcode", "school_mpesa_accounts", ["shortcode"])
    op.create_index(
        "ux_school_mpesa_live_shortcode", "school_mpesa_accounts", ["shortcode"], unique=True,
        postgresql_where=sa.text("environment = 'PRODUCTION'"),
    )

    # Owner-only. RLS on with NO policy denies everyone but the table owner; the REVOKE removes the privileges too
    # (the RLS script's default privileges would otherwise hand them to ledgr_app). Two locks, not one.
    op.execute("ALTER TABLE school_mpesa_accounts ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $$
        DECLARE r text;
        BEGIN
          FOREACH r IN ARRAY ARRAY['ledgr_app', 'anon', 'authenticated'] LOOP
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
              EXECUTE format('REVOKE ALL ON TABLE school_mpesa_accounts FROM %I', r);
            END IF;
          END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_table("school_mpesa_accounts")
    op.drop_column("mpesa_transactions", "business_shortcode")
    op.drop_column("schools", "mpesa_mode")

"""phone-number login for every role: canonical phone key + index

Revision ID: a8f3c1d6e2b9
Revises: f7d2b5e9a3c8
Create Date: 2026-09-22 00:00:00.000000

Parents type their phone number in many formats ("0712 345 678",
"+254712345678", ...). ledgr_phone_key() reduces any of them to one canonical
digit string so a sign-in by phone finds the account however it was stored,
and the functional index keeps that lookup fast. The same rules live in
app/core/phone.py::phone_key — keep them identical.
"""

from alembic import op

revision = "a8f3c1d6e2b9"
down_revision = "f7d2b5e9a3c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION ledgr_phone_key(p text) RETURNS text
        LANGUAGE sql IMMUTABLE
        SET search_path = pg_catalog, pg_temp
        AS $$
          SELECT CASE
            WHEN d = '' THEN NULL
            WHEN d LIKE '00%' THEN substr(d, 3)
            WHEN d LIKE '0%' THEN '254' || substr(d, 2)
            WHEN d LIKE '254%' AND length(d) >= 12 THEN d
            WHEN length(d) IN (9, 10) AND left(d, 1) IN ('7', '1') THEN '254' || d
            ELSE d
          END
          FROM (SELECT regexp_replace(coalesce(p, ''), '\D', '', 'g') AS d) t
        $$
        """
    )
    # Not callable through the Supabase Data API roles; the app roles still can.
    op.execute("REVOKE ALL ON FUNCTION ledgr_phone_key(text) FROM PUBLIC")
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ledgr_app') THEN
            GRANT EXECUTE ON FUNCTION ledgr_phone_key(text) TO ledgr_app;
          END IF;
        END
        $$;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_phone_key ON users (ledgr_phone_key(phone)) WHERE phone IS NOT NULL")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_phone_key")
    op.execute("DROP FUNCTION IF EXISTS ledgr_phone_key(text)")

"""enable RLS on typing_status and lock the public schema away from the Supabase Data API

Revision ID: b7e3d9f1c2a5
Revises: a1d5c7e9b2f4
Create Date: 2026-09-19 00:00:00.000000

Fixes Supabase Advisor "RLS Disabled in Public: public.typing_status".
typing_status was added by a later migration and was never included in
sql/enable_rls.sql, so it sat in the public schema with RLS off — readable
and writable by anyone holding the project's public anon key via Supabase's
auto-generated REST API.

This migration:
  1. Enables RLS on typing_status and gives it the same tenant_isolation
     policy as every other tenant table (restricted ledgr_app role only).
  2. Revokes all table/sequence/function access in `public` from Supabase's
     `anon` and `authenticated` roles. Ledgr never uses the Supabase Data API
     (the backend talks to Postgres directly), so nothing legitimate is lost,
     and any table added in future can no longer be exposed by accident.

Both steps are guarded so the migration is a no-op on a plain Postgres that
doesn't have those roles (local dev).
"""

from alembic import op

revision = "b7e3d9f1c2a5"
down_revision = "a1d5c7e9b2f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE typing_status ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ledgr_app') THEN
            DROP POLICY IF EXISTS tenant_isolation ON typing_status;
            CREATE POLICY tenant_isolation ON typing_status FOR ALL TO ledgr_app
              USING (school_id = (select current_setting('app.current_school_id', true))::text)
              WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);
          END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        DECLARE r text;
        BEGIN
          FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
              EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', r);
              EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', r);
              EXECUTE format('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM %I', r);
              EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I', r);
              EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I', r);
              EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM %I', r);
            END IF;
          END LOOP;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON typing_status")
    op.execute("ALTER TABLE typing_status DISABLE ROW LEVEL SECURITY")
    # The anon/authenticated revokes are deliberately NOT undone — re-granting
    # public access to every table would re-open the hole this migration closed.

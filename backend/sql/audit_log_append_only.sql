-- Makes audit_logs APPEND-ONLY: rows can be added and read, never changed or removed.
--
-- Run ONCE in the Supabase SQL Editor (it runs as the postgres owner role). Safe to re-run.
-- enable_rls.sql contains the same block, so a fresh setup gets this automatically.
--
-- Two layers, so one mistake can't undo the other:
--   1. The app role (ledgr_app) loses UPDATE / DELETE / TRUNCATE, and its row-level
--      policy shrinks from "everything" to "see and add your own school's rows".
--   2. A trigger rejects UPDATE / DELETE / TRUNCATE for EVERYONE, including the
--      postgres role that the login / webhook endpoints connect as. Only a
--      superuser deliberately dropping the trigger can get around it.

REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM ledgr_app;

DROP POLICY IF EXISTS tenant_isolation ON audit_logs;
DROP POLICY IF EXISTS tenant_read ON audit_logs;
DROP POLICY IF EXISTS tenant_insert ON audit_logs;
CREATE POLICY tenant_read ON audit_logs FOR SELECT TO ledgr_app
  USING (school_id = (select current_setting('app.current_school_id', true))::text);
CREATE POLICY tenant_insert ON audit_logs FOR INSERT TO ledgr_app
  WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);

CREATE OR REPLACE FUNCTION ledgr_audit_log_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_logs is append-only: % is not allowed', TG_OP
    USING ERRCODE = '42501';
END;
$$;

DROP TRIGGER IF EXISTS audit_logs_no_update_delete ON audit_logs;
CREATE TRIGGER audit_logs_no_update_delete
  BEFORE UPDATE OR DELETE ON audit_logs
  FOR EACH ROW EXECUTE FUNCTION ledgr_audit_log_immutable();

DROP TRIGGER IF EXISTS audit_logs_no_truncate ON audit_logs;
CREATE TRIGGER audit_logs_no_truncate
  BEFORE TRUNCATE ON audit_logs
  FOR EACH STATEMENT EXECUTE FUNCTION ledgr_audit_log_immutable();

-- ============================================================================
-- Row-Level Security setup for Ledgr
-- ============================================================================
-- This is the file referenced throughout the codebase (core/database.py,
-- core/deps.py get_school_scope) as the second, database-level layer of
-- tenant isolation — the app already filters every query by school_id at
-- the application layer; this makes Postgres enforce the identical rule
-- independently, so a bug in the app layer can't leak one school's data to
-- another.
--
-- HOW TO RUN THIS
-- Run as the table owner (the role behind DATABASE_URL — in Supabase, the
-- "postgres" role, or run it directly in the Supabase SQL Editor, which
-- already has owner privileges). Never run this as the restricted
-- ledgr_app role created below — it won't have permission to do most of
-- what's here, by design.
--
--   psql "$DATABASE_URL" -f sql/enable_rls.sql
--
-- AFTER RUNNING THIS
-- Set APP_DATABASE_URL in your .env to a connection string using the
-- ledgr_app role this script creates (same host/port/database as
-- DATABASE_URL, different user/password). Until APP_DATABASE_URL is set,
-- core/database.py falls back to DATABASE_URL (the owner role), which
-- bypasses RLS entirely — the policies below will exist but won't
-- actually restrict anything until that connection string is switched.
--
-- Safe to re-run: every statement below is idempotent (IF NOT EXISTS /
-- CREATE OR REPLACE / DROP POLICY IF EXISTS before CREATE POLICY).
--
-- Update: policies now wrap current_setting() in a (select ...) subquery
-- per Supabase's "Auth RLS Initialization Plan" advisory — without it,
-- Postgres re-evaluates current_setting() once per ROW scanned instead of
-- once per query, which gets slow as tables grow. Also added RLS on
-- alembic_version (Alembic's own bookkeeping table, not tenant data — see
-- the comment where it's enabled below). If you already ran an earlier
-- version of this file, just re-run this one; DROP POLICY IF EXISTS
-- handles the upgrade cleanly.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1. The restricted role every normal request runs as
-- ----------------------------------------------------------------------------
-- No BYPASSRLS, no table-owner privileges — just enough to do exactly what
-- the FastAPI app does: read/write rows, nothing at the schema level.
-- Replace 'change-me-before-running' with a real secret before running
-- this in production, or rotate it immediately after with ALTER ROLE.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ledgr_app') THEN
    CREATE ROLE ledgr_app LOGIN PASSWORD 's#BDZySwd705qM*h34$U';
  END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO ledgr_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ledgr_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ledgr_app;


-- ----------------------------------------------------------------------------
-- 2. Enable RLS on every table
-- ----------------------------------------------------------------------------
-- Once enabled, a table with NO matching policy denies all access by
-- default — so every table here needs a policy below, or the app breaks
-- for it, not just becomes insecure.

ALTER TABLE schools ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE terms ENABLE ROW LEVEL SECURITY;
ALTER TABLE school_classes ENABLE ROW LEVEL SECURITY;
ALTER TABLE students ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_guardians ENABLE ROW LEVEL SECURITY;
ALTER TABLE fee_structures ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_reminder_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_plan_installments ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_risk_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE mpesa_transactions ENABLE ROW LEVEL SECURITY;

-- alembic_version isn't tenant data — it's a single-row table Alembic
-- itself uses to track which migration the schema is currently at. It
-- gets no policy below, so it's enabled-but-deny-all for ledgr_app: the
-- app never has any legitimate reason to touch it (only `alembic upgrade`,
-- run as the owner role, does). This satisfies Supabase's "every public
-- table needs RLS" check without pretending this table has a tenant.
ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY;


-- ----------------------------------------------------------------------------
-- 3. Policies — tables with a direct school_id column
-- ----------------------------------------------------------------------------
-- The standard shape: a request may only see/write rows whose school_id
-- matches the session's app.current_school_id, which get_school_scope()
-- sets at the start of every tenant-scoped request (see core/deps.py).
-- current_setting(..., true) returns NULL rather than erroring when unset,
-- so a request with no tenant context (see "Known limitations" below)
-- matches nothing — fails closed, not open.

DROP POLICY IF EXISTS tenant_isolation ON schools;
CREATE POLICY tenant_isolation ON schools FOR ALL TO ledgr_app
  USING (id = (select current_setting('app.current_school_id', true))::text)
  WITH CHECK (id = (select current_setting('app.current_school_id', true))::text);

DROP POLICY IF EXISTS tenant_isolation ON users;
CREATE POLICY tenant_isolation ON users FOR ALL TO ledgr_app
  USING (school_id = (select current_setting('app.current_school_id', true))::text)
  WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);

DROP POLICY IF EXISTS tenant_isolation ON terms;
CREATE POLICY tenant_isolation ON terms FOR ALL TO ledgr_app
  USING (school_id = (select current_setting('app.current_school_id', true))::text)
  WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);

DROP POLICY IF EXISTS tenant_isolation ON school_classes;
CREATE POLICY tenant_isolation ON school_classes FOR ALL TO ledgr_app
  USING (school_id = (select current_setting('app.current_school_id', true))::text)
  WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);

DROP POLICY IF EXISTS tenant_isolation ON students;
CREATE POLICY tenant_isolation ON students FOR ALL TO ledgr_app
  USING (school_id = (select current_setting('app.current_school_id', true))::text)
  WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);

DROP POLICY IF EXISTS tenant_isolation ON fee_structures;
CREATE POLICY tenant_isolation ON fee_structures FOR ALL TO ledgr_app
  USING (school_id = (select current_setting('app.current_school_id', true))::text)
  WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);

DROP POLICY IF EXISTS tenant_isolation ON invoices;
CREATE POLICY tenant_isolation ON invoices FOR ALL TO ledgr_app
  USING (school_id = (select current_setting('app.current_school_id', true))::text)
  WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);

DROP POLICY IF EXISTS tenant_isolation ON invoice_reminder_logs;
CREATE POLICY tenant_isolation ON invoice_reminder_logs FOR ALL TO ledgr_app
  USING (school_id = (select current_setting('app.current_school_id', true))::text)
  WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);

DROP POLICY IF EXISTS tenant_isolation ON payments;
CREATE POLICY tenant_isolation ON payments FOR ALL TO ledgr_app
  USING (school_id = (select current_setting('app.current_school_id', true))::text)
  WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);

DROP POLICY IF EXISTS tenant_isolation ON audit_logs;
CREATE POLICY tenant_isolation ON audit_logs FOR ALL TO ledgr_app
  USING (school_id = (select current_setting('app.current_school_id', true))::text)
  WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);

DROP POLICY IF EXISTS tenant_isolation ON payment_plans;
CREATE POLICY tenant_isolation ON payment_plans FOR ALL TO ledgr_app
  USING (school_id = (select current_setting('app.current_school_id', true))::text)
  WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);

DROP POLICY IF EXISTS tenant_isolation ON messages;
CREATE POLICY tenant_isolation ON messages FOR ALL TO ledgr_app
  USING (school_id = (select current_setting('app.current_school_id', true))::text)
  WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);

DROP POLICY IF EXISTS tenant_isolation ON invoice_risk_snapshots;
CREATE POLICY tenant_isolation ON invoice_risk_snapshots FOR ALL TO ledgr_app
  USING (school_id = (select current_setting('app.current_school_id', true))::text)
  WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);

DROP POLICY IF EXISTS tenant_isolation ON invoice_outcomes;
CREATE POLICY tenant_isolation ON invoice_outcomes FOR ALL TO ledgr_app
  USING (school_id = (select current_setting('app.current_school_id', true))::text)
  WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);


-- ----------------------------------------------------------------------------
-- 4. Policies — child tables with no direct school_id column
-- ----------------------------------------------------------------------------
-- These inherit their tenant from a parent row instead of carrying their
-- own school_id (invoice_items -> invoices, payment_plan_installments ->
-- payment_plans, student_guardians -> students). Same isolation, enforced
-- via a join to the parent's already-protected school_id.

DROP POLICY IF EXISTS tenant_isolation ON invoice_items;
CREATE POLICY tenant_isolation ON invoice_items FOR ALL TO ledgr_app
  USING (EXISTS (
    SELECT 1 FROM invoices
    WHERE invoices.id = invoice_items.invoice_id
      AND invoices.school_id = (select current_setting('app.current_school_id', true))::text
  ))
  WITH CHECK (EXISTS (
    SELECT 1 FROM invoices
    WHERE invoices.id = invoice_items.invoice_id
      AND invoices.school_id = (select current_setting('app.current_school_id', true))::text
  ));

DROP POLICY IF EXISTS tenant_isolation ON payment_plan_installments;
CREATE POLICY tenant_isolation ON payment_plan_installments FOR ALL TO ledgr_app
  USING (EXISTS (
    SELECT 1 FROM payment_plans
    WHERE payment_plans.id = payment_plan_installments.plan_id
      AND payment_plans.school_id = (select current_setting('app.current_school_id', true))::text
  ))
  WITH CHECK (EXISTS (
    SELECT 1 FROM payment_plans
    WHERE payment_plans.id = payment_plan_installments.plan_id
      AND payment_plans.school_id = (select current_setting('app.current_school_id', true))::text
  ));

DROP POLICY IF EXISTS tenant_isolation ON student_guardians;
CREATE POLICY tenant_isolation ON student_guardians FOR ALL TO ledgr_app
  USING (EXISTS (
    SELECT 1 FROM students
    WHERE students.id = student_guardians.student_id
      AND students.school_id = (select current_setting('app.current_school_id', true))::text
  ))
  WITH CHECK (EXISTS (
    SELECT 1 FROM students
    WHERE students.id = student_guardians.student_id
      AND students.school_id = (select current_setting('app.current_school_id', true))::text
  ));


-- ----------------------------------------------------------------------------
-- 5. mpesa_transactions — deliberately more permissive
-- ----------------------------------------------------------------------------
-- school_id is nullable here (see models/mpesa_transaction.py): a direct
-- paybill payment arrives with no invoice reference yet, so it can't be
-- attributed to a school until a bursar matches it (routers/mpesa.py
-- reconciliation endpoints). Until matched, EVERY school's bursars need to
-- be able to see it to search/claim it — restricting unmatched rows to one
-- school would make the reconciliation feature unable to find anything.
-- Once matched (school_id is set), normal tenant isolation applies.

DROP POLICY IF EXISTS tenant_isolation ON mpesa_transactions;
CREATE POLICY tenant_isolation ON mpesa_transactions FOR ALL TO ledgr_app
  USING (school_id IS NULL OR school_id = (select current_setting('app.current_school_id', true))::text)
  WITH CHECK (school_id IS NULL OR school_id = (select current_setting('app.current_school_id', true))::text);


-- ============================================================================
-- Known limitations
-- ============================================================================
-- 1. SUPER_ADMIN cross-tenant access. get_school_scope() intentionally
--    clears app.current_school_id for SUPER_ADMIN requests (see the
--    comment in core/deps.py) rather than restricting them to one school —
--    but these policies have no corresponding "bypass" clause, since
--    nothing here can safely distinguish a genuine SUPER_ADMIN request
--    from a request that simply forgot to set a school context. The
--    practical effect: with APP_DATABASE_URL set, SUPER_ADMIN-only
--    endpoints querying via get_db will see zero rows everywhere, not
--    cross-tenant data — it fails closed, but it does mean those specific
--    endpoints need fixing before APP_DATABASE_URL is turned on, or they
--    silently stop working for the platform-admin role. The fix mirrors
--    what routers/auth.py already does for pre-authentication endpoints:
--    switch those specific routes to get_system_db (the unrestricted
--    owner-role connection) rather than get_db — their trust model is
--    "the JWT says SUPER_ADMIN", not "RLS scoped them correctly", which is
--    a legitimate but different guarantee, the same reasoning already
--    documented for the M-Pesa webhook callback in core/database.py.
--
-- 2. mpesa_transactions cross-tenant visibility while unmatched (see
--    section 5 above) is deliberate, not a gap — flagging it here so it
--    isn't mistaken for one during a future security review.
-- ============================================================================

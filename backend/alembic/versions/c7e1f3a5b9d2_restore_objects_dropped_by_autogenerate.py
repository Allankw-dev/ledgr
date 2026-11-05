"""Make sure nothing the previous (now neutralised) migration used to drop is missing.

Revision ID: c7e1f3a5b9d2
Revises: 6dedb9109fcc

Why this exists: 6dedb9109fcc was committed as raw `alembic revision --autogenerate` output. It did not add
anything; it DROPPED two tables (invoice_outcomes, invoice_risk_snapshots), about 40 indexes (including the unique
guards ux_payments_external_txn_id, uq_users_teacher_phone, ux_guardian_invites_* and the passkey credential_id
uniqueness) because Alembic could not see them in the models. 6dedb9109fcc is now a no-op, so a database that
never ran the destructive version needs nothing from this file. A database that DID run it gets everything put
back. Every statement is "if missing", so running it on a healthy database changes nothing. (Rows that were in the
two dropped ML tables cannot be recovered by a migration: restore those from a backup if you need them.)
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c7e1f3a5b9d2"
down_revision = "6dedb9109fcc"
branch_labels = None
depends_on = None

# Exact definitions copied from a database built by the migrations up to a6c9d2e5f8b1.
INDEXES = [
    'CREATE INDEX IF NOT EXISTS ix_audit_logs_school_created ON audit_logs USING btree (school_id, created_at DESC)',
    'CREATE INDEX IF NOT EXISTS ix_class_group_mentions_message ON class_group_mentions USING btree (message_id)',
    'CREATE INDEX IF NOT EXISTS ix_cgm_class_created ON class_group_messages USING btree (class_id, created_at DESC)',
    'CREATE INDEX IF NOT EXISTS ix_class_group_read_state_user ON class_group_read_state USING btree (user_id)',
    'CREATE INDEX IF NOT EXISTS ix_direct_blocks_blocked ON direct_blocks USING btree (blocked_user_id)',
    'CREATE INDEX IF NOT EXISTS ix_direct_messages_unread ON direct_messages USING btree (conversation_id) WHERE (read_at IS NULL)',
    'CREATE INDEX IF NOT EXISTS ix_fee_structures_school_term ON fee_structures USING btree (school_id, term_id)',
    'CREATE UNIQUE INDEX IF NOT EXISTS ux_guardian_invites_student_email ON guardian_invites USING btree (student_id, lower((email)::text)) WHERE (email IS NOT NULL)',
    'CREATE UNIQUE INDEX IF NOT EXISTS ux_guardian_invites_student_phone ON guardian_invites USING btree (student_id, ledgr_phone_key((phone)::text)) WHERE (phone IS NOT NULL)',
    'CREATE INDEX IF NOT EXISTS ix_invoice_reminder_logs_invoice_tier ON invoice_reminder_logs USING btree (invoice_id, tier)',
    'CREATE INDEX IF NOT EXISTS ix_invoices_school_status_due ON invoices USING btree (school_id, status, due_date)',
    'CREATE INDEX IF NOT EXISTS ix_invoices_school_term ON invoices USING btree (school_id, term_id)',
    'CREATE INDEX IF NOT EXISTS ix_invoices_student_status ON invoices USING btree (student_id, status)',
    'CREATE INDEX IF NOT EXISTS ix_messages_thread ON messages USING btree (school_id, parent_user_id, created_at DESC)',
    'CREATE INDEX IF NOT EXISTS ix_mpesa_transactions_status_created ON mpesa_transactions USING btree (status, created_at DESC)',
    'CREATE INDEX IF NOT EXISTS ix_payments_invoice_status ON payments USING btree (invoice_id, status) INCLUDE (amount)',
    'CREATE INDEX IF NOT EXISTS ix_payments_school_created ON payments USING btree (school_id, created_at DESC)',
    'CREATE INDEX IF NOT EXISTS ix_payments_school_status ON payments USING btree (school_id, status)',
    'CREATE UNIQUE INDEX IF NOT EXISTS ux_payments_external_txn_id ON payments USING btree (external_txn_id) WHERE (external_txn_id IS NOT NULL)',
    'CREATE INDEX IF NOT EXISTS ix_school_classes_school ON school_classes USING btree (school_id)',
    'CREATE INDEX IF NOT EXISTS ix_student_guardians_student_status ON student_guardians USING btree (student_id, status)',
    'CREATE INDEX IF NOT EXISTS ix_student_guardians_user_status ON student_guardians USING btree (user_id, status)',
    'CREATE INDEX IF NOT EXISTS ix_students_admission_number ON students USING btree (admission_number)',
    'CREATE INDEX IF NOT EXISTS ix_students_school_admission ON students USING btree (school_id, admission_number)',
    'CREATE INDEX IF NOT EXISTS ix_students_school_class ON students USING btree (school_id, class_id)',
    'CREATE INDEX IF NOT EXISTS ix_teacher_class_assignments_class ON teacher_class_assignments USING btree (class_id)',
    'CREATE INDEX IF NOT EXISTS ix_teacher_class_assignments_teacher ON teacher_class_assignments USING btree (teacher_user_id)',
    'CREATE INDEX IF NOT EXISTS ix_terms_school ON terms USING btree (school_id)',
    'CREATE INDEX IF NOT EXISTS ix_users_phone_key ON users USING btree (ledgr_phone_key((phone)::text)) WHERE (phone IS NOT NULL)',
    'CREATE INDEX IF NOT EXISTS ix_users_school_role ON users USING btree (school_id, role)',
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_teacher_phone ON users USING btree (phone) WHERE ((role = 'TEACHER'::userrole) AND (phone IS NOT NULL))",
    'CREATE INDEX IF NOT EXISTS ix_webauthn_challenges_expires_at ON webauthn_challenges USING btree (expires_at)',
]

# Indexes of the two ML tables; created after the tables below.
ML_INDEXES = [
    'CREATE UNIQUE INDEX IF NOT EXISTS ix_invoice_outcomes_invoice_id ON invoice_outcomes USING btree (invoice_id)',
    'CREATE INDEX IF NOT EXISTS ix_invoice_outcomes_school_id ON invoice_outcomes USING btree (school_id)',
    'CREATE INDEX IF NOT EXISTS ix_invoice_risk_snapshots_invoice_id ON invoice_risk_snapshots USING btree (invoice_id)',
    'CREATE INDEX IF NOT EXISTS ix_invoice_risk_snapshots_school_id ON invoice_risk_snapshots USING btree (school_id)',
]

# Row-level security for the two tables, exactly as sql/enable_rls.sql sets it up. Only where the app's restricted
# role exists (it does not on a plain development database). Safe to repeat: the policy is dropped and recreated.
_POLICY = (
    "FOR ALL TO ledgr_app "
    "USING (school_id = (select current_setting('app.current_school_id', true))::text) "
    "WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text)"
)
RLS_SQL = (
    "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ledgr_app') THEN "
    "ALTER TABLE invoice_risk_snapshots ENABLE ROW LEVEL SECURITY; "
    "ALTER TABLE invoice_outcomes ENABLE ROW LEVEL SECURITY; "
    "DROP POLICY IF EXISTS tenant_isolation ON invoice_risk_snapshots; "
    f"CREATE POLICY tenant_isolation ON invoice_risk_snapshots {_POLICY}; "
    "DROP POLICY IF EXISTS tenant_isolation ON invoice_outcomes; "
    f"CREATE POLICY tenant_isolation ON invoice_outcomes {_POLICY}; "
    "GRANT SELECT, INSERT, UPDATE, DELETE ON invoice_risk_snapshots, invoice_outcomes TO ledgr_app; "
    "END IF; END $$"
)


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    # The enum type outlives a dropped table, so create it only when it is really missing.
    op.execute(
        "DO $$ BEGIN CREATE TYPE invoiceoutcomelabel AS ENUM ('PAID_ON_TIME', 'PAID_LATE', 'DEFAULTED'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )

    if "invoice_risk_snapshots" not in tables:
        op.create_table(
            "invoice_risk_snapshots",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("invoice_id", sa.String(), nullable=False),
            sa.Column("school_id", sa.String(), nullable=False),
            sa.Column("taken_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.Column("history_score", sa.Float(), nullable=False),
            sa.Column("overdue_score", sa.Float(), nullable=False),
            sa.Column("balance_score", sa.Float(), nullable=False),
            sa.Column("reversal_score", sa.Float(), nullable=False),
            sa.Column("total_score", sa.Float(), nullable=False),
            sa.Column("risk_level", sa.String(), nullable=False),
            sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], name="invoice_risk_snapshots_invoice_id_fkey"),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"], name="invoice_risk_snapshots_school_id_fkey"),
            sa.PrimaryKeyConstraint("id", name="invoice_risk_snapshots_pkey"),
        )
    if "invoice_outcomes" not in tables:
        op.create_table(
            "invoice_outcomes",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("invoice_id", sa.String(), nullable=False),
            sa.Column("school_id", sa.String(), nullable=False),
            sa.Column(
                "outcome",
                postgresql.ENUM("PAID_ON_TIME", "PAID_LATE", "DEFAULTED", name="invoiceoutcomelabel", create_type=False),
                nullable=False,
            ),
            sa.Column("days_late", sa.Integer(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], name="invoice_outcomes_invoice_id_fkey"),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"], name="invoice_outcomes_school_id_fkey"),
            sa.PrimaryKeyConstraint("id", name="invoice_outcomes_pkey"),
            sa.UniqueConstraint("invoice_id", name="invoice_outcomes_invoice_id_key"),
        )

    # Passkey credential ids must stay unique.
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'webauthn_credentials_credential_id_key') THEN "
        "ALTER TABLE webauthn_credentials ADD CONSTRAINT webauthn_credentials_credential_id_key UNIQUE (credential_id); "
        "END IF; END $$"
    )

    for statement in INDEXES + ML_INDEXES:
        op.execute(statement)

    op.execute(RLS_SQL)


def downgrade() -> None:
    # Deliberately empty: putting the safety indexes back is never something to undo.
    pass

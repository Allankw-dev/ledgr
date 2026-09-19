"""add composite/foreign-key indexes for common query paths

Revision ID: a1d5c7e9b2f4
Revises: c9f2b6a4d813
Create Date: 2026-09-19 00:00:00.000000

Every statement is CREATE INDEX IF NOT EXISTS, so this is safe to re-run and
safe if an index was already added by hand in the Supabase dashboard.

What each one is for:
  students(school_id, admission_number)      M-Pesa C2B matching, lookups by admission no.
  students(admission_number)                 C2B matching before the school is known
  students(school_id, class_id)              per-grade lists / broadcasts
  student_guardians(user_id, status)         parent portal: "which children are mine?"
  student_guardians(student_id, status)      reminders, notifications, message validation
  invoices(school_id, status, due_date)      overdue sweep, dashboards, bursar lists
  invoices(school_id, term_id)               per-term reports/exports
  invoices(student_id, status)               a student's open invoices (payments, C2B)
  payments(school_id, created_at)            recent-payment lists, anomaly checks
  payments(school_id, status)                confirmed/pending filters
  invoice_reminder_logs(invoice_id, tier)    overdue sweep "highest tier already sent"
  messages(school_id, parent_user_id, created_at)  thread fetch (polled every few seconds)
  audit_logs(school_id, created_at)          audit log viewer (newest first)
  fee_structures(school_id, term_id)         invoice generation
  mpesa_transactions(status, created_at)     reconciliation queue
  terms / school_classes (school_id)         lookups by school
"""

from alembic import op

revision = "a1d5c7e9b2f4"
down_revision = "c9f2b6a4d813"
branch_labels = None
depends_on = None

INDEXES = [
    ("ix_students_school_admission", "students", "school_id, admission_number"),
    ("ix_students_admission_number", "students", "admission_number"),
    ("ix_students_school_class", "students", "school_id, class_id"),
    ("ix_student_guardians_user_status", "student_guardians", "user_id, status"),
    ("ix_student_guardians_student_status", "student_guardians", "student_id, status"),
    ("ix_invoices_school_status_due", "invoices", "school_id, status, due_date"),
    ("ix_invoices_school_term", "invoices", "school_id, term_id"),
    ("ix_invoices_student_status", "invoices", "student_id, status"),
    ("ix_payments_school_created", "payments", "school_id, created_at DESC"),
    ("ix_payments_school_status", "payments", "school_id, status"),
    ("ix_invoice_reminder_logs_invoice_tier", "invoice_reminder_logs", "invoice_id, tier"),
    ("ix_messages_thread", "messages", "school_id, parent_user_id, created_at DESC"),
    ("ix_audit_logs_school_created", "audit_logs", "school_id, created_at DESC"),
    ("ix_fee_structures_school_term", "fee_structures", "school_id, term_id"),
    ("ix_mpesa_transactions_status_created", "mpesa_transactions", "status, created_at DESC"),
    ("ix_terms_school", "terms", "school_id"),
    ("ix_school_classes_school", "school_classes", "school_id"),
]


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")


def downgrade() -> None:
    for name, _table, _columns in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")

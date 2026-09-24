"""guardian invites: phone is the primary match key, email becomes optional

Revision ID: c1f8a3e6b4d2
Revises: a4f1e8c3b6d9
Create Date: 2026-09-23 00:00:00.000000

Flips which contact detail is required when a bursar records a parent
against a student: phone is now the one that's always collected (this is
a Kenyan school app built around M-Pesa and SMS reminders — a phone
number is the reliable constant, an email often isn't), email is
optional. Enforced in the API schema (CreateStudentRequest /
LinkGuardianRequest), not as a DB NOT NULL on phone — existing invite
rows created under the old rules may have no phone on file and there's
no way to backfill one, so the DB stays permissive there.

What actually changes at the DB layer:
  - email becomes nullable, since a bursar can now leave it out entirely
  - the old case-insensitive unique index on (student_id, lower(email))
    is rebuilt as a PARTIAL index (WHERE email IS NOT NULL), so several
    invites for the same student with no email don't collide
  - a matching partial unique index goes on (student_id,
    ledgr_phone_key(phone)) — phone is now how a returning parent's
    signup gets matched to an invite, same normalized-key approach
    already used for phone login (see a8f3c1d6e2b9)
"""

from alembic import op

revision = "c1f8a3e6b4d2"
down_revision = "a4f1e8c3b6d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE guardian_invites ALTER COLUMN email DROP NOT NULL")

    op.execute("DROP INDEX IF EXISTS ux_guardian_invites_student_email")
    op.execute(
        "CREATE UNIQUE INDEX ux_guardian_invites_student_email "
        "ON guardian_invites (student_id, lower(email)) WHERE email IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX ux_guardian_invites_student_phone "
        "ON guardian_invites (student_id, ledgr_phone_key(phone)) WHERE phone IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_guardian_invites_student_phone")
    op.execute("DROP INDEX IF EXISTS ux_guardian_invites_student_email")
    op.execute(
        "CREATE UNIQUE INDEX ux_guardian_invites_student_email ON guardian_invites (student_id, lower(email))"
    )
    # Any row with a NULL email created while this migration was applied
    # would violate the constraint being restored here — no way around
    # that on downgrade.
    op.execute("ALTER TABLE guardian_invites ALTER COLUMN email SET NOT NULL")

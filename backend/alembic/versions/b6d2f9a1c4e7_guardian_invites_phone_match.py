"""guardian invites: match by phone + name instead of email

Revision ID: b6d2f9a1c4e7
Revises: a4f1e8c3b6d9
Create Date: 2026-09-23 00:00:00.000000

Bursars often don't have a parent's email on hand but always have their
phone (it's what's on the enrollment form). Switches the invite/match key
for "Add student" and "Link parent" from email to phone number, checked
together with the guardian's full name at link time.

guardian_invites is a short-lived working table (rows are consumed the
moment they produce a match, or replaced if a bursar re-enters details) —
existing rows are cleared rather than backfilled, since there's no email-
to-phone data to backfill FROM.
"""

import sqlalchemy as sa
from alembic import op

revision = "b6d2f9a1c4e7"
down_revision = "a4f1e8c3b6d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_guardian_invites_student_email")
    op.execute("DELETE FROM guardian_invites")
    op.drop_column("guardian_invites", "email")
    op.add_column("guardian_invites", sa.Column("phone", sa.String(), nullable=False))
    op.create_index("ix_guardian_invites_phone", "guardian_invites", ["phone"])
    # One outstanding invite per (student, phone) — same reasoning as the
    # email version this replaces.
    op.create_unique_constraint(
        "ux_guardian_invites_student_phone", "guardian_invites", ["student_id", "phone"]
    )


def downgrade() -> None:
    op.drop_constraint("ux_guardian_invites_student_phone", "guardian_invites", type_="unique")
    op.drop_index("ix_guardian_invites_phone", table_name="guardian_invites")
    op.drop_column("guardian_invites", "phone")
    op.add_column("guardian_invites", sa.Column("email", sa.String(), nullable=False, server_default=""))
    op.alter_column("guardian_invites", "email", server_default=None)
    op.execute(
        "CREATE UNIQUE INDEX ux_guardian_invites_student_email "
        "ON guardian_invites (student_id, lower(email))"
    )

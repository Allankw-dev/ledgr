"""guardian invites — bursar-vouched parent email, no admin-set password

Revision ID: a4f1e8c3b6d9
Revises: d3a7e1c5f9b2
Create Date: 2026-09-23 00:00:00.000000

Lets a bursar record a parent's expected email/name/phone against a
student — either right when the student is added, or later via "Link
parent" — WITHOUT setting a password on their behalf. When that email
later self-registers and links to the same student, the link is
auto-approved and this row is consumed. Same tenant-isolation (RLS)
pattern as every other school-scoped table.
"""

import sqlalchemy as sa
from alembic import op

revision = "a4f1e8c3b6d9"
down_revision = "d3a7e1c5f9b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guardian_invites",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("school_id", sa.String(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("student_id", sa.String(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("relationship_type", sa.String(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_guardian_invites_school_id", "guardian_invites", ["school_id"])
    op.create_index("ix_guardian_invites_student_id", "guardian_invites", ["student_id"])
    # Case-insensitive match against the email a parent signs up with; one
    # outstanding invite per (student, email) so a bursar re-linking the
    # same parent twice just hits the existing "already invited" check
    # instead of piling up duplicate rows.
    op.execute(
        "CREATE UNIQUE INDEX ux_guardian_invites_student_email "
        "ON guardian_invites (student_id, lower(email))"
    )

    op.execute("ALTER TABLE guardian_invites ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ledgr_app') THEN
            DROP POLICY IF EXISTS tenant_isolation ON guardian_invites;
            CREATE POLICY tenant_isolation ON guardian_invites FOR ALL TO ledgr_app
              USING (school_id = (select current_setting('app.current_school_id', true))::text)
              WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);
          END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.drop_table("guardian_invites")

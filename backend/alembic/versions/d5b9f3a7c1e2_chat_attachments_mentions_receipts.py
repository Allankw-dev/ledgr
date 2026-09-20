"""class group chat: attachments, @mentions, delivery receipts, phone-only teachers

Revision ID: d5b9f3a7c1e2
Revises: c4a8e2b6d0f3
Create Date: 2026-09-20 00:00:00.000000

Idempotent (IF NOT EXISTS everywhere). The new class_group_mentions table is
created WITH row-level security and the standard tenant policy in the same
migration — new tables must never exist in `public` without RLS (that is
exactly what the Supabase Advisor flagged for typing_status).
"""

from alembic import op

revision = "d5b9f3a7c1e2"
down_revision = "c4a8e2b6d0f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE class_group_messages ADD COLUMN IF NOT EXISTS attachment_key VARCHAR")
    op.execute("ALTER TABLE class_group_messages ADD COLUMN IF NOT EXISTS attachment_name VARCHAR")
    op.execute("ALTER TABLE class_group_messages ADD COLUMN IF NOT EXISTS attachment_mime VARCHAR")
    op.execute("ALTER TABLE class_group_messages ADD COLUMN IF NOT EXISTS attachment_size INTEGER")
    op.execute("ALTER TABLE class_group_messages ALTER COLUMN body SET DEFAULT ''")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cgm_class_created ON class_group_messages (class_id, created_at DESC)")

    op.execute("ALTER TABLE class_group_read_state ADD COLUMN IF NOT EXISTS last_delivered_at TIMESTAMPTZ")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS class_group_mentions (
            id VARCHAR PRIMARY KEY,
            school_id VARCHAR NOT NULL REFERENCES schools(id),
            class_id VARCHAR NOT NULL REFERENCES school_classes(id),
            message_id VARCHAR NOT NULL REFERENCES class_group_messages(id) ON DELETE CASCADE,
            mentioned_user_id VARCHAR NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            seen_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_class_group_mentions_school_id ON class_group_mentions (school_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_class_group_mentions_message ON class_group_mentions (message_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_class_group_mentions_user_seen ON class_group_mentions (mentioned_user_id, seen_at)"
    )
    op.execute("ALTER TABLE class_group_mentions ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ledgr_app') THEN
            DROP POLICY IF EXISTS tenant_isolation ON class_group_mentions;
            CREATE POLICY tenant_isolation ON class_group_mentions FOR ALL TO ledgr_app
              USING (school_id = (select current_setting('app.current_school_id', true))::text)
              WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);
            GRANT SELECT, INSERT, UPDATE, DELETE ON class_group_mentions TO ledgr_app;
          END IF;
        END
        $$;
        """
    )

    # Teachers can now log in with a phone number, so a teacher's phone must be
    # unique across the whole platform (login has no school context).
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_teacher_phone ON users (phone) "
        "WHERE role = 'TEACHER' AND phone IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_users_teacher_phone")
    op.execute("DROP TABLE IF EXISTS class_group_mentions")
    op.execute("ALTER TABLE class_group_read_state DROP COLUMN IF EXISTS last_delivered_at")
    op.execute("DROP INDEX IF EXISTS ix_cgm_class_created")
    for col in ("attachment_key", "attachment_name", "attachment_mime", "attachment_size"):
        op.execute(f"ALTER TABLE class_group_messages DROP COLUMN IF EXISTS {col}")

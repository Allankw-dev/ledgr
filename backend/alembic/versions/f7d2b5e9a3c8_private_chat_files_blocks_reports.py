"""private chats: encrypted files, delete-for-everyone, blocking, reporting

Revision ID: f7d2b5e9a3c8
Revises: e6c1a4d8f2b7
Create Date: 2026-09-22 00:00:00.000000
"""

from alembic import op

revision = "f7d2b5e9a3c8"
down_revision = "e6c1a4d8f2b7"
branch_labels = None
depends_on = None

NEW_TABLES = ("direct_blocks", "direct_reports")


def upgrade() -> None:
    op.execute("ALTER TABLE direct_messages ADD COLUMN IF NOT EXISTS attachment_enc TEXT")
    op.execute("ALTER TABLE direct_messages ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS direct_blocks (
            id VARCHAR PRIMARY KEY,
            school_id VARCHAR NOT NULL REFERENCES schools(id),
            blocker_user_id VARCHAR NOT NULL REFERENCES users(id),
            blocked_user_id VARCHAR NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_direct_block_pair UNIQUE (blocker_user_id, blocked_user_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_direct_blocks_school_id ON direct_blocks (school_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_direct_blocks_blocked ON direct_blocks (blocked_user_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS direct_reports (
            id VARCHAR PRIMARY KEY,
            school_id VARCHAR NOT NULL REFERENCES schools(id),
            conversation_id VARCHAR NOT NULL REFERENCES direct_conversations(id) ON DELETE CASCADE,
            reporter_user_id VARCHAR NOT NULL REFERENCES users(id),
            reported_user_id VARCHAR NOT NULL REFERENCES users(id),
            category VARCHAR NOT NULL,
            details_enc TEXT,
            evidence_enc TEXT NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'OPEN',
            resolution_note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            resolved_at TIMESTAMPTZ,
            resolved_by VARCHAR
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_direct_reports_school_id ON direct_reports (school_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_direct_reports_school_status ON direct_reports (school_id, status)")

    for t in NEW_TABLES:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            DO $$
            BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ledgr_app') THEN
                DROP POLICY IF EXISTS tenant_isolation ON {t};
                CREATE POLICY tenant_isolation ON {t} FOR ALL TO ledgr_app
                  USING (school_id = (select current_setting('app.current_school_id', true))::text)
                  WITH CHECK (school_id = (select current_setting('app.current_school_id', true))::text);
                GRANT SELECT, INSERT, UPDATE, DELETE ON {t} TO ledgr_app;
              END IF;
            END
            $$;
            """
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS direct_reports")
    op.execute("DROP TABLE IF EXISTS direct_blocks")
    op.execute("ALTER TABLE direct_messages DROP COLUMN IF EXISTS deleted_at")
    op.execute("ALTER TABLE direct_messages DROP COLUMN IF EXISTS attachment_enc")

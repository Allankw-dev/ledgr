"""private teacher <-> parent chats (encrypted at rest)

Revision ID: e6c1a4d8f2b7
Revises: d5b9f3a7c1e2
Create Date: 2026-09-21 00:00:00.000000

Both tables are created WITH row-level security and the standard tenant
policy in the same migration. Who-can-read-which-conversation (only the two
participants) is enforced in the API layer on top of that.
"""

from alembic import op

revision = "e6c1a4d8f2b7"
down_revision = "d5b9f3a7c1e2"
branch_labels = None
depends_on = None

TABLES = ("direct_conversations", "direct_messages")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS direct_conversations (
            id VARCHAR PRIMARY KEY,
            school_id VARCHAR NOT NULL REFERENCES schools(id),
            teacher_user_id VARCHAR NOT NULL REFERENCES users(id),
            parent_user_id VARCHAR NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_direct_conversation_pair UNIQUE (teacher_user_id, parent_user_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_direct_conversations_school_id ON direct_conversations (school_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_direct_conversations_parent ON direct_conversations (parent_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_direct_conversations_teacher ON direct_conversations (teacher_user_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS direct_messages (
            id VARCHAR PRIMARY KEY,
            school_id VARCHAR NOT NULL REFERENCES schools(id),
            conversation_id VARCHAR NOT NULL REFERENCES direct_conversations(id) ON DELETE CASCADE,
            sender_user_id VARCHAR NOT NULL REFERENCES users(id),
            body_enc TEXT NOT NULL,
            key_version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            delivered_at TIMESTAMPTZ,
            read_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_direct_messages_school_id ON direct_messages (school_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_direct_messages_conv_created ON direct_messages (conversation_id, created_at)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_direct_messages_unread ON direct_messages (conversation_id) WHERE read_at IS NULL"
    )

    for t in TABLES:
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
    op.execute("DROP TABLE IF EXISTS direct_messages")
    op.execute("DROP TABLE IF EXISTS direct_conversations")

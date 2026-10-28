"""one account per email, ignoring case

Revision ID: f3c5e7a9b1d4
Revises: e1b3c5d7f9a2

The app now compares emails case-insensitively. This adds the matching database guard: a unique index on
lower(email). If the data already holds two accounts whose emails differ only by case, the index cannot be
built, so this migration prints them and skips the index instead of failing the deploy. Fix those rows by
hand (merge or rename one), then create the index yourself:
    CREATE UNIQUE INDEX ux_users_email_lower ON users (lower(email));
(`alembic upgrade head` will not retry it, because this revision is already recorded as applied.)
"""

from alembic import op
import sqlalchemy as sa

revision = "f3c5e7a9b1d4"
down_revision = "e1b3c5d7f9a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    dupes = conn.execute(
        sa.text("SELECT lower(email), count(*) FROM users GROUP BY lower(email) HAVING count(*) > 1")
    ).fetchall()
    if dupes:
        print(
            "\n*** ux_users_email_lower NOT created: these emails exist more than once when case is ignored: "
            + ", ".join(f"{row[0]} (x{row[1]})" for row in dupes)
            + "\n*** Merge or rename those accounts, then run: "
            "CREATE UNIQUE INDEX ux_users_email_lower ON users (lower(email));\n"
        )
        return
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email_lower ON users (lower(email))")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_users_email_lower")

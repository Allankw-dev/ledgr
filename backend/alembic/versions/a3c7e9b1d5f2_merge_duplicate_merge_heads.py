"""Join the two merge migrations that were added in parallel

d4a9e2c6f1b8 and d9f2a6b8c4e1 are both "merge b8e4c1d7a2f3 + c7e1f3a5b9d2" and both do nothing, but because each
was added separately the history had two heads again. This revision joins them. Neither earlier file is deleted or
edited, so it is safe whichever of them a database has already recorded as its current revision.

Revision ID: a3c7e9b1d5f2
Revises: d4a9e2c6f1b8, d9f2a6b8c4e1
Create Date: 2026-11-06 09:00:00.000000

"""

revision = "a3c7e9b1d5f2"
down_revision = ("d4a9e2c6f1b8", "d9f2a6b8c4e1")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

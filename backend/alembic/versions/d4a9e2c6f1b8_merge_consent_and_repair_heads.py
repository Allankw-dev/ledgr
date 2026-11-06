"""Merge the consent/opt-out/deletion migration with the 6dedb repair migration

Two migrations were written in parallel, both on top of 6dedb9109fcc:
  b8e4c1d7a2f3  adds consent, email opt-out and deletion columns to users
  c7e1f3a5b9d2  restores the objects 6dedb9109fcc wrongly dropped
They touch different things, so this merge changes nothing itself. It only makes the history a single line again,
which `alembic upgrade head` needs. Safe whichever of the two has already been applied.

Revision ID: d4a9e2c6f1b8
Revises: b8e4c1d7a2f3, c7e1f3a5b9d2
Create Date: 2026-11-05 14:00:00.000000

"""

revision = "d4a9e2c6f1b8"
down_revision = ("b8e4c1d7a2f3", "c7e1f3a5b9d2")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

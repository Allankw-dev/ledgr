"""merge ml training-data branch with overdue reminder automation branch

Revision ID: f4d8e1c6a930
Revises: 66d455a92fdf, b3f1a9c02e77
Create Date: 2026-09-06 09:00:00.000000

"""

revision = "f4d8e1c6a930"
down_revision = ("66d455a92fdf", "b3f1a9c02e77")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No schema changes of its own — this just joins the two branches
    # (ML training-data tables, and overdue reminder automation) that both
    # forked off 90b11f4d1d34, so there's a single head again.
    pass


def downgrade() -> None:
    pass

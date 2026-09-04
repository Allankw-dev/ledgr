"""add guardian link status

Revision ID: 90b11f4d1d34
Revises: c530e54f39f1
Create Date: 2026-08-24 01:15:07.170440

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "90b11f4d1d34"
down_revision = "c530e54f39f1"
branch_labels = None
depends_on = None

guardian_link_status = postgresql.ENUM(
    "PENDING",
    "APPROVED",
    "REJECTED",
    name="guardianlinkstatus",
)


def upgrade() -> None:
    guardian_link_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "student_guardians",
        sa.Column(
            "status",
            guardian_link_status,
            server_default="APPROVED",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("student_guardians", "status")
    guardian_link_status.drop(op.get_bind(), checkfirst=True)

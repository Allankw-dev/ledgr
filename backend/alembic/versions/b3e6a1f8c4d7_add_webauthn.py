"""add webauthn credentials and challenges for fingerprint/biometric login

Revision ID: b3e6a1f8c4d7
Revises: a7c3f5e9b1d2
Create Date: 2026-09-13 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "b3e6a1f8c4d7"
down_revision = "a7c3f5e9b1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webauthn_credentials",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        # credential_id is what the authenticator hands back on every
        # login to say "this is me" — base64url text, not raw bytes, so
        # it's directly usable in a WHERE clause and JSON responses without
        # extra encode/decode ceremony.
        sa.Column("credential_id", sa.String(), nullable=False, unique=True),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("device_name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_webauthn_credentials_user_id", "webauthn_credentials", ["user_id"])
    op.create_index("ix_webauthn_credentials_credential_id", "webauthn_credentials", ["credential_id"], unique=True)

    # Short-lived — a WebAuthn challenge is single-use and expires in
    # minutes, so this table is really a small queue, not permanent data.
    # user_id is nullable: set for a registration challenge (we already
    # know who's enrolling a fingerprint), null for a login challenge
    # (discoverable/usernameless — we don't know who's signing in until
    # their authenticator tells us via the credential_id in the response).
    op.create_table(
        "webauthn_challenges",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("challenge", sa.LargeBinary(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),  # "registration" | "authentication"
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_webauthn_challenges_expires_at", "webauthn_challenges", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_webauthn_challenges_expires_at", table_name="webauthn_challenges")
    op.drop_table("webauthn_challenges")

    op.drop_index("ix_webauthn_credentials_credential_id", table_name="webauthn_credentials")
    op.drop_index("ix_webauthn_credentials_user_id", table_name="webauthn_credentials")
    op.drop_table("webauthn_credentials")

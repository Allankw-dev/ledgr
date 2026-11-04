from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.school import gen_uuid


class SchoolMpesaAccount(Base):
    """One school's OWN M-Pesa (Daraja) paybill details.

    The key, secret and passkey are stored ONLY as ciphertext (core/secret_crypto.py), bound to this school so a
    row copied to another school fails to decrypt. They are write-only through the API: nothing ever returns them.

    This table is deliberately OWNER-ONLY: the restricted `ledgr_app` role used for ordinary requests has no
    privileges on it and no policy (see the migration and sql/enable_rls.sql). Every read goes through
    services/mpesa_accounts.py on a separate system session, so even a bug or injection in a normal request
    cannot reach another school's, or this school's, credentials.
    """

    __tablename__ = "school_mpesa_accounts"
    __table_args__ = (
        UniqueConstraint("school_id", name="uq_school_mpesa_accounts_school"),
        # A LIVE paybill belongs to exactly one school, so a payment arriving on it can only be that school's.
        # Sandbox accounts may share Safaricom's public test shortcode, so uniqueness is only for production.
        Index("ux_school_mpesa_live_shortcode", "shortcode", unique=True, postgresql_where=text("environment = 'PRODUCTION'")),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String, nullable=False)  # SANDBOX | PRODUCTION
    shortcode: Mapped[str] = mapped_column(String, nullable=False, index=True)
    consumer_key_enc: Mapped[str] = mapped_column(Text, nullable=False)
    consumer_secret_enc: Mapped[str] = mapped_column(Text, nullable=False)
    passkey_enc: Mapped[str] = mapped_column(Text, nullable=False)
    # Bumping this invalidates every webhook address previously given to Safaricom for this school.
    callback_token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    c2b_registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)  # a fixed, non-sensitive message, never a Safaricom body
    updated_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

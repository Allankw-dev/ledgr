from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.school import gen_uuid


class RefreshToken(Base):
    """One row per issued refresh token. The token itself is never stored,
    only its SHA-256 — a database leak can't be replayed as live sessions.

    Tokens are single-use: every refresh rotates to a new row in the same
    `family_id` (one family = one sign-in on one device). Presenting a token
    that was already rotated, outside a short grace window, means it was
    copied — so the whole family is revoked and that sign-in must start over.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    family_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    # users.token_version at issue time — a password reset / email change
    # bumps the user's version, which invalidates every refresh token issued before it.
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # Hard cap for the whole family, so rotating can't keep a session alive forever.
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

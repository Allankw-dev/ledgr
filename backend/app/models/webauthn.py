from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Integer, LargeBinary, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.school import gen_uuid


class WebAuthnCredential(Base):
    """One row per fingerprint/Face ID/Windows Hello enrollment. A user can
    have several — a phone and a laptop each register their own credential,
    same as how WhatsApp Web lets you have multiple linked devices."""

    __tablename__ = "webauthn_credentials"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    credential_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # Every authentication ceremony returns a sign count that must only
    # ever increase — a count that goes backward or repeats is the classic
    # signal an authenticator was cloned, which verify_authentication_response
    # checks against this stored value.
    sign_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    device_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WebAuthnChallenge(Base):
    """A pending WebAuthn ceremony's server-generated challenge, held just
    long enough for the browser round-trip to the authenticator and back.
    Deleted the moment it's used (or once expired) — this table should
    stay tiny at all times, not accumulate."""

    __tablename__ = "webauthn_challenges"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    challenge: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    purpose: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

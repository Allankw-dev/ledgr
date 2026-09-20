from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Integer, func, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.school import gen_uuid


class ClassGroupMessage(Base):
    """One broadcast thread per grade — every parent with a child in that
    grade, plus every teacher assigned to it and the bursar's office, share
    a single running conversation. This is deliberately unlike Message
    (app/models/message.py), which is a private 1:1 thread between one
    parent and the school; this is the "class WhatsApp group" equivalent —
    everyone in the class sees every message.

    sender_role isn't stored here — who's allowed to post, and how their
    name/role badge is displayed, is derived by joining sender_user_id back
    to users at query time. That keeps this table from ever going stale if
    someone's role changes, and avoids a second place a role has to be kept
    in sync."""

    __tablename__ = "class_group_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    class_id: Mapped[str] = mapped_column(ForeignKey("school_classes.id"), nullable=False, index=True)
    sender_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    # Empty string (not NULL) for attachment-only messages.
    body: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")

    # Optional single attachment (photo or file). The bytes live in storage
    # (see services/storage_service.py) — only its key and display metadata
    # are kept here. mime is derived server-side from the validated file
    # type, never trusted from the client.
    attachment_key: Mapped[str | None] = mapped_column(String, nullable=True)
    attachment_name: Mapped[str | None] = mapped_column(String, nullable=True)
    attachment_mime: Mapped[str | None] = mapped_column(String, nullable=True)
    attachment_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class ClassGroupMention(Base):
    """One row per (message, mentioned person). Powers the "X mentioned you"
    notification: a row with seen_at NULL is an unseen mention. Viewing the
    thread marks that class's mentions seen, same "viewing IS reading"
    pattern the rest of the chat uses."""

    __tablename__ = "class_group_mentions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    class_id: Mapped[str] = mapped_column(ForeignKey("school_classes.id"), nullable=False)
    message_id: Mapped[str] = mapped_column(ForeignKey("class_group_messages.id", ondelete="CASCADE"), nullable=False)
    mentioned_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_class_group_mentions_user_seen", "mentioned_user_id", "seen_at"),)

from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.school import gen_uuid


class DirectConversation(Base):
    """A private conversation between exactly one teacher and one parent.
    Unlike Message (a shared parent<->school inbox) and ClassGroupMessage
    (everyone in a grade), only these two people can read it — not other
    staff, not the school admin."""

    __tablename__ = "direct_conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    teacher_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    parent_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("teacher_user_id", "parent_user_id", name="uq_direct_conversation_pair"),
        Index("ix_direct_conversations_parent", "parent_user_id"),
        Index("ix_direct_conversations_teacher", "teacher_user_id"),
    )


class DirectMessage(Base):
    """One message. The text exists ONLY as ciphertext (body_enc) — see
    app/core/message_crypto.py. delivered_at = the recipient's app fetched it;
    read_at = the recipient opened the conversation."""

    __tablename__ = "direct_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("direct_conversations.id", ondelete="CASCADE"), nullable=False)
    sender_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    body_enc: Mapped[str] = mapped_column(Text, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Encrypted JSON {"key", "name", "mime", "size"} for a photo/file. The file
    # itself lives in storage as ciphertext; even its name is not readable here.
    attachment_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "Delete for everyone": the content is wiped (body_enc replaced, file
    # removed) and this is set, so the chat shows "This message was deleted".
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_direct_messages_conv_created", "conversation_id", "created_at"),)


class DirectBlock(Base):
    """blocker_user_id has blocked blocked_user_id: neither can send messages
    in their private chat until it's undone. The blocked person isn't told."""

    __tablename__ = "direct_blocks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    blocker_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    blocked_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("blocker_user_id", "blocked_user_id", name="uq_direct_block_pair"),)


class DirectReport(Base):
    """A report of a private chat, reviewed by the school admin. It carries an
    ENCRYPTED snapshot of the recent messages taken at report time, so the
    admin sees exactly what was reported (and only that — not the whole chat),
    even if the sender later deletes those messages."""

    __tablename__ = "direct_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("direct_conversations.id", ondelete="CASCADE"), nullable=False)
    reporter_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    reported_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    details_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_enc: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="OPEN")  # OPEN | REVIEWING | RESOLVED | DISMISSED
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (Index("ix_direct_reports_school_status", "school_id", "status"),)

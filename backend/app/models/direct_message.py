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

    __table_args__ = (Index("ix_direct_messages_conv_created", "conversation_id", "created_at"),)

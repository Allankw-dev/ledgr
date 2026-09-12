from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Text
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
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

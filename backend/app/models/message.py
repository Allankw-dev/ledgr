from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Enum as SAEnum, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.school import gen_uuid
from app.models.enums import MessageSenderRole


class Message(Base):
    """
    One flat conversation per (school, parent) — not per student, since a
    parent with more than one child at the school should have a single
    thread with the bursar's office rather than one per kid. student_id is
    optional context on a message (which child a question is about), not
    the thread key.

    Every message — from either side — carries parent_user_id so the whole
    conversation, regardless of who's writing, is one query away. read_by_*
    are independent: a staff reply doesn't mark itself read by the parent,
    and vice versa — each side's unread count is exactly what messages the
    OTHER side sent that this side hasn't opened yet.
    """

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    parent_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    student_id: Mapped[str | None] = mapped_column(ForeignKey("students.id"), nullable=True)

    sender_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    sender_role: Mapped[MessageSenderRole] = mapped_column(SAEnum(MessageSenderRole), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    read_by_parent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_by_staff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.school import gen_uuid


class ClassGroupReadState(Base):
    """One row per (user, class) — the last time that user opened that
    grade's group thread. This is what powers the unread badge: any
    ClassGroupMessage with created_at after this timestamp counts as
    unread for them. Updated as a side effect of fetching the thread (see
    class_groups.py), the same pattern the 1:1 Message model already uses
    for read_by_parent_at/read_by_staff_at — viewing IS marking as read,
    there's no separate "mark read" action to remember to call."""

    __tablename__ = "class_group_read_state"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    class_id: Mapped[str] = mapped_column(ForeignKey("school_classes.id"), nullable=False)
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "class_id", name="uq_class_group_read_state"),)

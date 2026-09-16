from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TypingStatus(Base):
    """One row per (school, parent) conversation, tracking the most recent
    keystroke timestamp reported by each side.

    There's no websocket layer in this app, so "is the other person typing"
    is answered by polling rather than pushing: the composing side pings
    this row (debounced client-side to roughly once every couple of
    seconds), and the other side polls a lightweight status endpoint that
    just checks whether that ping is still "fresh" (within the last few
    seconds). That means the indicator clears itself automatically once
    the person stops typing, with no separate stop-typing event needed.
    """

    __tablename__ = "typing_status"

    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), primary_key=True)
    parent_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)

    parent_typing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    staff_typing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

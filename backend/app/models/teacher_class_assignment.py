from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.school import gen_uuid


class TeacherClassAssignment(Base):
    """Which grades a teacher teaches — a many-to-many join, since a subject
    teacher can be assigned to more than one grade, and a grade's class
    group chat should include every teacher assigned to it, not just one
    "homeroom" teacher. This is what determines a teacher's membership in
    a grade's class group (see class_group.py for the access-check logic
    that reads this table)."""

    __tablename__ = "teacher_class_assignments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    teacher_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    class_id: Mapped[str] = mapped_column(ForeignKey("school_classes.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("teacher_user_id", "class_id", name="uq_teacher_class"),)

from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, ForeignKey, func, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.school import gen_uuid
from app.models.enums import GuardianLinkStatus


class Term(Base):
    __tablename__ = "terms"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "Term 1 2026"
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SchoolClass(Base):
    __tablename__ = "school_classes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "Grade 4"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    class_id: Mapped[str | None] = mapped_column(ForeignKey("school_classes.id"), nullable=True)
    admission_number: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    date_of_birth: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    school_class: Mapped["SchoolClass | None"] = relationship()


class StudentGuardian(Base):
    """Many-to-many: a student can have multiple guardians (parents),
    and one guardian account can be linked to multiple students (siblings).

    status defaults to APPROVED because links created by a bursar (who is
    already trusted and already looking at the real student record) don't
    need a review step — only links a PARENT creates themselves, by typing
    in an admission number they could have gotten from anywhere, start out
    PENDING and require a bursar to confirm before any real data is shown."""

    __tablename__ = "student_guardians"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String, nullable=False)  # "mother", "father", "guardian"
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[GuardianLinkStatus] = mapped_column(
        SAEnum(GuardianLinkStatus), default=GuardianLinkStatus.APPROVED, server_default="APPROVED", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GuardianInvite(Base):
    """A parent's expected name + phone, captured by a bursar — either while
    adding the student, or later via 'Link parent' — for a parent who
    doesn't have an account yet. No password (and no email) is ever set
    here; the bursar is only vouching that this name and phone belong to
    this student's parent.

    When someone later self-registers (choosing their own email and
    password) and links to this student, matching this SAME phone number
    AND full name, the self-service link is auto-approved instead of
    sitting in the bursar's review queue, and this row is consumed
    (deleted). If either doesn't match, the normal PENDING review flow
    applies untouched — a phone number alone is too easy to mistype or
    guess to grant access on its own."""

    __tablename__ = "guardian_invites"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, nullable=False, index=True)  # normalized E.164, e.g. +254712345678
    relationship_type: Mapped[str] = mapped_column(String, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

"""Bulk parent communication — send a school-wide or class-wide notice
(not tied to a specific invoice) to every guardian with an APPROVED link,
reusing the same email/SMS delivery as fee reminders. Deliberately
excludes PENDING guardian links, same reasoning as the per-invoice
reminder: an unconfirmed link isn't a verified point of contact yet."""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import GuardianLinkStatus
from app.models.school import User
from app.models.student import Student, StudentGuardian
from app.services.notification_service import send_message_to_guardian


@dataclass
class AnnouncementResult:
    recipient_count: int
    emails_sent: int
    sms_sent: int
    errors: list[str] = field(default_factory=list)


def send_bulk_announcement(
    db: Session,
    school_id: str,
    school_name: str,
    subject: str,
    message: str,
    class_id: str | None = None,
) -> AnnouncementResult:
    student_filters = [Student.school_id == school_id, Student.is_active == True]  # noqa: E712
    if class_id:
        student_filters.append(Student.class_id == class_id)

    student_ids = db.execute(select(Student.id).where(*student_filters)).scalars().all()
    if not student_ids:
        return AnnouncementResult(recipient_count=0, emails_sent=0, sms_sent=0)

    guardian_ids = (
        db.execute(
            select(StudentGuardian.user_id)
            .where(
                StudentGuardian.student_id.in_(student_ids),
                StudentGuardian.status == GuardianLinkStatus.APPROVED,
            )
            .distinct()  # a guardian with two children in the filtered set is messaged once, not twice
        )
        .scalars()
        .all()
    )

    email_subject = f"{school_name}: {subject}"
    email_body = f"Dear Parent/Guardian,\n\n{message}\n\nThank you,\n{school_name}"
    sms_text = f"{school_name}: {message}"

    emails_sent = 0
    sms_sent = 0
    errors: list[str] = []

    for guardian_id in guardian_ids:
        guardian = db.get(User, guardian_id)
        if not guardian:
            continue
        outcome = send_message_to_guardian(
            guardian_email=guardian.email,
            guardian_phone=guardian.phone,
            email_subject=email_subject,
            email_body=email_body,
            sms_text=sms_text,
        )
        if outcome.email_sent:
            emails_sent += 1
        if outcome.sms_sent:
            sms_sent += 1
        errors.extend(outcome.errors)

    return AnnouncementResult(
        recipient_count=len(guardian_ids),
        emails_sent=emails_sent,
        sms_sent=sms_sent,
        errors=errors,
    )

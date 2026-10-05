"""Bulk parent communication — send a school-wide or class-wide notice
(not tied to a specific invoice) to every guardian with an APPROVED link,
reusing the same email/SMS delivery as fee reminders. Deliberately
excludes PENDING guardian links, same reasoning as the per-invoice
reminder: an unconfirmed link isn't a verified point of contact yet."""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import GuardianLinkStatus
from app.models.student import Student, StudentGuardian
from app.core.jobs import enqueue_many
from app.services.job_handlers import guardian_message_jobs


@dataclass
class AnnouncementResult:
    recipient_count: int
    jobs_queued: int
    errors: list[str] = field(default_factory=list)


def send_bulk_announcement(
    db: Session,
    school_id: str,
    school_name: str,
    subject: str,
    message: str,
    class_id: str | None = None,
    class_ids: list[str] | None = None,
) -> AnnouncementResult:
    student_filters = [Student.school_id == school_id, Student.is_active == True]  # noqa: E712
    targets = list(dict.fromkeys([*(class_ids or []), *([class_id] if class_id else [])]))
    if targets:
        student_filters.append(Student.class_id.in_(targets))

    # One query for the guardians (a join, not a giant "student id IN (...)" list): for a school of
    # thousands that list alone was a very large statement.
    guardian_ids = (
        db.execute(
            select(StudentGuardian.user_id)
            .join(Student, Student.id == StudentGuardian.student_id)
            .where(*student_filters, StudentGuardian.status == GuardianLinkStatus.APPROVED)
            .distinct()  # a guardian with two children in the filtered set is messaged once, not twice
        )
        .scalars()
        .all()
    )
    if not guardian_ids:
        return AnnouncementResult(recipient_count=0, jobs_queued=0)

    email_subject = f"{school_name}: {subject}"
    email_body = f"Dear Parent/Guardian,\n\n{message}\n\nThank you,\n{school_name}"
    sms_text = f"{school_name}: {message}"

    # Queued as durable jobs rather than sent synchronously: a broadcast can
    # reach hundreds of guardians, and looping SMTP/SMS calls inside the
    # request would hold the connection open for minutes and abandon whatever
    # hadn't sent yet if the request timed out or the worker restarted.
    # dedupe_key ties each job to THIS specific announcement (content-hashed),
    # so retrying the request after a timeout can't double-message anyone.
    from app.core.idempotency import natural_key  # local import — avoids a cycle at module load time

    batch_key = natural_key(school_id, subject, message, sorted(guardian_ids))
    jobs_queued = 0
    for i in range(0, len(guardian_ids), 500):  # one INSERT per 500 guardians (1,000 jobs), not one per job
        rows: list[dict] = []
        for guardian_id in guardian_ids[i : i + 500]:
            rows.extend(
                guardian_message_jobs(
                    school_id=school_id,
                    guardian_id=guardian_id,
                    email_subject=email_subject,
                    email_body=email_body,
                    sms_text=sms_text,
                    dedupe_prefix=f"announce:{batch_key}",
                )
            )
        jobs_queued += len(enqueue_many(db, rows))
    errors: list[str] = []

    return AnnouncementResult(
        recipient_count=len(guardian_ids),
        jobs_queued=jobs_queued,
        errors=errors,
    )

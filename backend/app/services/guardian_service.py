"""Guardian linking — shared by parent self-signup (auto-link, when the
bursar already registered this parent's name + phone against a student)
and the standalone verify-child flow (same matching rules, used when a
parent adds a second child, or signed up before being invited)."""

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.student import Student, StudentGuardian, GuardianInvite
from app.models.enums import GuardianLinkStatus


def normalize_name(name: str) -> str:
    """Case/whitespace-insensitive comparison key for guardian names —
    'Wanjiru  Otieno' and 'wanjiru otieno' should match without forcing
    exact formatting."""
    return " ".join(name.strip().lower().split())


def find_active_student_by_admission(db: Session, school_id: str, admission_number: str) -> Student | None:
    return db.execute(
        select(Student).where(
            func.lower(Student.admission_number) == admission_number.strip().lower(),
            Student.school_id == school_id,
            Student.is_active == True,  # noqa: E712
        )
    ).scalar_one_or_none()


def link_or_request_guardian(
    db: Session,
    *,
    student_id: str,
    user_id: str,
    full_name: str,
    phone: str | None,
    relationship_type: str,
) -> tuple[StudentGuardian, bool]:
    """Creates a StudentGuardian link from user_id to student_id.

    Auto-approves and consumes a matching GuardianInvite — same phone
    number AND same name — if one exists for this exact student, since
    that means a bursar already vouched for this parent. Otherwise creates
    a PENDING link for a bursar to review by hand. Does not commit; the
    caller controls the transaction. Returns (guardian, auto_approved).
    """
    invite = None
    if phone:
        candidate = db.execute(
            select(GuardianInvite).where(GuardianInvite.student_id == student_id, GuardianInvite.phone == phone)
        ).scalar_one_or_none()
        if candidate and normalize_name(candidate.full_name) == normalize_name(full_name):
            invite = candidate

    guardian = StudentGuardian(
        student_id=student_id,
        user_id=user_id,
        # On a match, trust what the bursar actually recorded (e.g.
        # "mother") over whatever default the caller passed in.
        relationship_type=invite.relationship_type if invite else relationship_type,
        is_primary=True,
        status=GuardianLinkStatus.APPROVED if invite else GuardianLinkStatus.PENDING,
    )
    db.add(guardian)
    if invite:
        db.delete(invite)
    return guardian, invite is not None

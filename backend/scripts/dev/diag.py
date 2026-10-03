"""Quick look at schools / recent parent signups / students (read-only).

    cd backend
    python -m scripts.dev.diag

Personal data is masked on purpose, so pasting the output into a chat or a
bug report doesn't leak real parents' emails and phone numbers.
"""

from app.core.database import SystemSessionLocal
from app.models.school import School, User
from app.models.student import Student
from app.models.enums import UserRole


def mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return "-"
    name, _, domain = email.partition("@")
    return f"{name[:1]}***@{domain}"


def mask_phone(phone: str | None) -> str:
    if not phone:
        return "-"
    return f"{'*' * max(len(phone) - 3, 0)}{phone[-3:]}"


db = SystemSessionLocal()

print('--- schools ---')
for s in db.query(School).all():
    print(s.id, s.name)

print('--- recent parent signups ---')
for u in db.query(User).filter(User.role == UserRole.PARENT).order_by(User.created_at.desc()).limit(5):
    print(u.id, u.full_name, mask_email(u.email), mask_phone(u.phone), 'school_id=', u.school_id)

print('--- students ---')
for s in db.query(Student).all():
    print(s.id, s.full_name, s.admission_number, 'school_id=', s.school_id, 'active=', s.is_active)

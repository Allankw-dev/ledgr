from app.core.database import SystemSessionLocal
from app.models.school import School, User
from app.models.student import Student
from app.models.enums import UserRole

db = SystemSessionLocal()

print('--- schools ---')
for s in db.query(School).all():
    print(s.id, s.name)

print('--- recent parent signups ---')
for u in db.query(User).filter(User.role == UserRole.PARENT).order_by(User.created_at.desc()).limit(5):
    print(u.id, u.full_name, u.email, u.phone, 'school_id=', u.school_id)

print('--- students ---')
for s in db.query(Student).all():
    print(s.id, s.full_name, s.admission_number, 'school_id=', s.school_id, 'active=', s.is_active)

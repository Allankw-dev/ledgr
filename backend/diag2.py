from app.core.database import SystemSessionLocal
from app.models.student import Student

db = SystemSessionLocal()

for s in db.query(Student).all():
    print(repr(s.admission_number), '| full_name=', repr(s.full_name), '| school_id=', s.school_id)

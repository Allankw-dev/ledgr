from sqlalchemy import select, func, text
from app.core.database import SessionLocal
from app.models.student import Student

SCHOOL_ID = '236e18c0-339a-419c-b243-4b4aaafdc502'

db = SessionLocal()
db.execute(text("SELECT set_config('app.current_school_id', :sid, true)"), {'sid': SCHOOL_ID})

result = db.execute(
    select(Student).where(
        func.lower(Student.admission_number) == '3005',
        Student.school_id == SCHOOL_ID,
        Student.is_active == True,
    )
).scalar_one_or_none()

print('Found via RLS-restricted connection:', result.full_name if result else None)

print('--- everything ledgr_app can see in students, unfiltered ---')
for s in db.execute(select(Student)).scalars().all():
    print(s.admission_number, s.full_name, s.school_id)

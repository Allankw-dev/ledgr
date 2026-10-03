"""Check what the restricted `ledgr_app` role (Row-Level Security) can see.

    cd backend
    python -m scripts.dev.diag3 <school_id> <admission_number>
"""

import sys

from sqlalchemy import select, func, text

from app.core.database import SessionLocal
from app.models.student import Student

if len(sys.argv) != 3:
    sys.exit("usage: python -m scripts.dev.diag3 <school_id> <admission_number>")
SCHOOL_ID, ADMISSION = sys.argv[1], sys.argv[2]

db = SessionLocal()
db.execute(text("SELECT set_config('app.current_school_id', :sid, true)"), {'sid': SCHOOL_ID})

result = db.execute(
    select(Student).where(
        func.lower(Student.admission_number) == ADMISSION.lower(),
        Student.school_id == SCHOOL_ID,
        Student.is_active == True,
    )
).scalar_one_or_none()

print('Found via RLS-restricted connection:', result.full_name if result else None)

print('--- everything ledgr_app can see in students, unfiltered ---')
for s in db.execute(select(Student)).scalars().all():
    print(s.admission_number, s.full_name, s.school_id)

"""Test setup.

Pure-logic tests (tokens, amount rules, crypto) run anywhere. Tests that touch
the database run only when TEST_DATABASE_URL points at a Postgres database whose
NAME CONTAINS "test" — they create and wipe tables, so they must never be pointed
at Supabase/production. Example (from backend/):

    createdb ledgr_test
    set TEST_DATABASE_URL=postgresql://postgres:password@localhost:5432/ledgr_test   (Windows)
    export TEST_DATABASE_URL=postgresql://postgres:password@localhost:5432/ledgr_test (Linux/macOS)
    pytest

The environment is overridden BEFORE the app is imported, so a developer's real
backend/.env (with its production-ish DATABASE_URL / APP_DATABASE_URL) can't leak in.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")

if TEST_DB_URL:
    _db_name = TEST_DB_URL.rsplit("/", 1)[-1].split("?")[0]
    if "test" not in _db_name.lower():
        raise RuntimeError(
            f"Refusing to run: TEST_DATABASE_URL database name {_db_name!r} must contain 'test' "
            "(the suite drops and recreates tables)."
        )

os.environ["DATABASE_URL"] = TEST_DB_URL or "postgresql://nobody:nothing@127.0.0.1:1/ledgr_test"
os.environ["APP_DATABASE_URL"] = os.environ["DATABASE_URL"]  # never fall through to a real .env value
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-123456"
os.environ["ENVIRONMENT"] = "development"
os.environ["REDIS_URL"] = ""
os.environ["SENTRY_DSN"] = ""
os.environ["MESSAGE_ENCRYPTION_KEYS"] = "1:" + "QUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUE="

needs_db = pytest.mark.skipif(not TEST_DB_URL, reason="set TEST_DATABASE_URL to a Postgres database named *test* to run")


@pytest.fixture(scope="session")
def _schema():
    if not TEST_DB_URL:
        pytest.skip("no TEST_DATABASE_URL")
    import app.models  # noqa: F401 — registers every table on Base.metadata
    from app.core.database import Base, system_engine

    Base.metadata.drop_all(system_engine)
    Base.metadata.create_all(system_engine)
    yield
    Base.metadata.drop_all(system_engine)


@pytest.fixture()
def db(_schema):
    """A fresh session on an empty database for every test."""
    from sqlalchemy import text
    from app.core.database import Base, SystemSessionLocal, system_engine

    with system_engine.begin() as conn:
        tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    session = SystemSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def world(db):
    """A school with a bursar, a parent, a student and one unpaid KES 10,000 invoice."""
    from app.models.invoice import Invoice
    from app.models.school import School, User
    from app.models.student import Student, Term
    from app.models.enums import InvoiceStatus, UserRole

    school = School(name="Test Academy", country="KE", contact_email="office@test.example")
    db.add(school)
    db.flush()
    bursar = User(
        school_id=school.id, email=f"b-{uuid.uuid4().hex[:6]}@test.example", password_hash="x",
        role=UserRole.BURSAR, full_name="Bursar",
    )
    parent = User(
        school_id=school.id, email=f"p-{uuid.uuid4().hex[:6]}@test.example", password_hash="x",
        role=UserRole.PARENT, full_name="Parent",
    )
    student = Student(school_id=school.id, admission_number="1001", full_name="Kid One")
    term = Term(
        school_id=school.id, name="Term 1", start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=90),
    )
    db.add_all([bursar, parent, student, term])
    db.flush()
    invoice = Invoice(
        school_id=school.id, student_id=student.id, term_id=term.id, total_amount=Decimal("10000.00"),
        due_date=datetime.now(timezone.utc) + timedelta(days=30), status=InvoiceStatus.ISSUED,
    )
    db.add(invoice)
    db.commit()

    class W:
        pass

    w = W()
    w.school, w.bursar, w.parent, w.student, w.term, w.invoice = school, bursar, parent, student, term, invoice
    return w

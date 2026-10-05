"""School-wide / class-wide announcements: who gets queued, once, and never the unverified."""

from sqlalchemy import func, select

from app.models.enums import GuardianLinkStatus, UserRole
from app.models.job import Job
from app.models.school import User
from app.models.student import SchoolClass, Student, StudentGuardian
from app.services.announcement_service import send_bulk_announcement
from tests.conftest import needs_db

pytestmark = needs_db


def _family(db, w, n, cls=None, status=GuardianLinkStatus.APPROVED, tag="f"):
    out = []
    for i in range(n):
        parent = User(school_id=w.school.id, email=f"{tag}{i}@test.example", password_hash="x", role=UserRole.PARENT, full_name=f"{tag}{i}")
        kid = Student(school_id=w.school.id, admission_number=f"{tag}{i}", full_name=f"{tag}-kid{i}", class_id=cls.id if cls else None)
        db.add_all([parent, kid])
        db.flush()
        db.add(StudentGuardian(student_id=kid.id, user_id=parent.id, relationship_type="mother", status=status))
        out.append((parent, kid))
    db.commit()
    return out


def _send(db, w, **kw):
    r = send_bulk_announcement(db, w.school.id, "Test Academy", "Fees", "Term fees are due Friday.", **kw)
    db.commit()
    return r


def _count(db):
    return db.execute(select(func.count()).select_from(Job)).scalar_one()


def test_every_approved_guardian_gets_an_email_and_an_sms_job(db, world):
    _family(db, world, 12)
    r = _send(db, world)
    assert (r.recipient_count, r.jobs_queued) == (12, 24)
    kinds = sorted(j.kind for j in db.execute(select(Job)).scalars())
    assert kinds.count("send_email") == 12 and kinds.count("send_sms") == 12


def test_class_filter(db, world):
    a, b = SchoolClass(school_id=world.school.id, name="A"), SchoolClass(school_id=world.school.id, name="B")
    db.add_all([a, b])
    db.commit()
    _family(db, world, 4, a, tag="a")
    _family(db, world, 3, b, tag="b")
    assert _send(db, world, class_id=a.id).recipient_count == 4
    assert _send(db, world, class_ids=[a.id, b.id]).recipient_count == 7


def test_unverified_guardians_are_never_messaged(db, world):
    _family(db, world, 3, status=GuardianLinkStatus.PENDING, tag="p")
    _family(db, world, 2, status=GuardianLinkStatus.REJECTED, tag="r")
    r = _send(db, world)
    assert (r.recipient_count, r.jobs_queued) == (0, 0) and _count(db) == 0


def test_a_guardian_with_two_children_is_messaged_once(db, world):
    [(parent, kid)] = _family(db, world, 1)
    kid2 = Student(school_id=world.school.id, admission_number="second", full_name="Second")
    db.add(kid2)
    db.flush()
    db.add(StudentGuardian(student_id=kid2.id, user_id=parent.id, relationship_type="mother", status=GuardianLinkStatus.APPROVED))
    db.commit()
    assert _send(db, world).recipient_count == 1 and _count(db) == 2


def test_resending_the_identical_announcement_queues_nothing_new(db, world):
    _family(db, world, 5)
    first = _send(db, world)
    again = _send(db, world)  # e.g. the bursar's request timed out and they clicked again
    assert first.jobs_queued == 10 and again.jobs_queued == 0 and _count(db) == 10


def test_inactive_students_are_skipped(db, world):
    [(parent, kid)] = _family(db, world, 1)
    kid.is_active = False
    db.commit()
    assert _send(db, world).recipient_count == 0


def test_more_than_one_chunk_of_guardians(db, world):
    _family(db, world, 520)  # crosses the 500-guardian insert boundary
    r = _send(db, world)
    assert (r.recipient_count, r.jobs_queued) == (520, 1040) and _count(db) == 1040

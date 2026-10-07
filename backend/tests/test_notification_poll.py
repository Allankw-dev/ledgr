"""The notification poll (GET /api/notifications/summary) runs every ~25 s for every logged-in
person, so it has two jobs: give the right numbers, and stay cheap. On a hosted database each
round trip is a network hop, and this endpoint once took 15 of them (3.7-6 s on production).
These tests pin down BOTH — the counts, the delivery ticks, and a round-trip budget — so a
future change can't quietly bring the cost back or break what the badges show.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core import database as dbm
from app.core.security import create_access_token
from app.main import app
from app.models.class_group_message import ClassGroupMention, ClassGroupMessage
from app.models.class_group_read_state import ClassGroupReadState
from app.models.direct_message import DirectConversation, DirectMessage
from app.models.enums import GuardianLinkStatus, MessageSenderRole, UserRole
from app.models.message import Message
from app.models.school import User
from app.models.student import SchoolClass, StudentGuardian
from tests.conftest import needs_db

pytestmark = needs_db

NOW = datetime.now(timezone.utc)


def _ago(**kw):
    return NOW - timedelta(**kw)


@pytest.fixture()
def scene(db, world):
    """A parent in Grade 4 with a known mix of read / unread / excluded messages."""
    cls = SchoolClass(school_id=world.school.id, name="Grade 4")
    other_cls = SchoolClass(school_id=world.school.id, name="Grade 7")
    db.add_all([cls, other_cls])
    db.flush()
    world.student.class_id = cls.id
    db.add(StudentGuardian(student_id=world.student.id, user_id=world.parent.id, relationship_type="mother",
                           status=GuardianLinkStatus.APPROVED))

    def msg(class_id, sender, when, body="hi"):
        m = ClassGroupMessage(school_id=world.school.id, class_id=class_id, sender_user_id=sender, body=body, created_at=when)
        db.add(m)
        return m

    last_read = _ago(hours=5)
    msg(cls.id, world.bursar.id, _ago(hours=9))                  # read (before last_read)
    msg(cls.id, world.bursar.id, _ago(hours=6))                  # read
    unread = [msg(cls.id, world.bursar.id, _ago(hours=h)) for h in (4, 3, 1)]  # 3 unread
    msg(cls.id, world.parent.id, _ago(hours=2))                  # the parent's own message: never "unread"
    msg(cls.id, world.bursar.id, _ago(days=120))                 # older than the 90-day window
    msg(other_cls.id, world.bursar.id, _ago(hours=1))            # a class the parent is not in
    db.add(ClassGroupReadState(user_id=world.parent.id, class_id=cls.id, last_read_at=last_read,
                               last_delivered_at=_ago(hours=5)))  # older than 3 of the messages -> there IS something new to record
    db.flush()
    for i, m in enumerate(unread):                               # 2 unseen mentions + 1 already seen
        db.add(ClassGroupMention(school_id=world.school.id, class_id=cls.id, message_id=m.id,
                                 mentioned_user_id=world.parent.id, seen_at=None if i < 2 else _ago(minutes=5)))

    for i in range(2):                                           # 2 unread messages from the school
        db.add(Message(school_id=world.school.id, parent_user_id=world.parent.id, student_id=world.student.id,
                       sender_user_id=world.bursar.id, sender_role=MessageSenderRole.STAFF, body=f"note {i}"))
    db.add(Message(school_id=world.school.id, parent_user_id=world.parent.id, student_id=world.student.id,
                   sender_user_id=world.bursar.id, sender_role=MessageSenderRole.STAFF, body="old", read_by_parent_at=_ago(days=1)))

    teacher = User(school_id=world.school.id, email=f"t-{uuid.uuid4().hex[:6]}@test.example", password_hash="x",
                   role=UserRole.TEACHER, full_name="Teacher")
    db.add(teacher)
    db.flush()
    convo = DirectConversation(school_id=world.school.id, teacher_user_id=teacher.id, parent_user_id=world.parent.id)
    db.add(convo)
    db.flush()
    for _ in range(2):                                           # 2 private messages from the teacher, not yet delivered
        db.add(DirectMessage(school_id=world.school.id, conversation_id=convo.id, sender_user_id=teacher.id, body_enc="x"))
    db.commit()

    class S:
        pass

    s = S()
    s.cls, s.convo, s.teacher, s.last_read = cls, convo, teacher, last_read
    return s


@pytest.fixture()
def parent_client(world):
    from app.core.rate_limit import limiter

    limiter.reset()
    c = TestClient(app)
    c.headers["Authorization"] = "Bearer " + create_access_token(world.parent.id, world.school.id, "PARENT")
    c.get("/api/notifications/summary")  # warm the per-process user cache so it isn't counted below
    yield c
    limiter.reset()


class _Meter:
    def __init__(self):
        self.statements, self.commits = [], 0

    def __enter__(self):
        event.listen(dbm.engine, "before_cursor_execute", self._s)
        event.listen(dbm.engine, "commit", self._c)
        return self

    def __exit__(self, *a):
        event.remove(dbm.engine, "before_cursor_execute", self._s)
        event.remove(dbm.engine, "commit", self._c)

    def _s(self, conn, cur, stmt, params, ctx, many):
        self.statements.append(re.sub(r"\s+", " ", stmt)[:80])

    def _c(self, conn):
        self.commits += 1

    @property
    def round_trips(self):
        return len(self.statements) + self.commits


def test_summary_counts_are_right(scene, parent_client):
    body = parent_client.get("/api/notifications/summary").json()
    assert body["unread_class_group_messages"] == 3   # only others' messages, after last_read, inside 90 days, own class
    assert body["unread_mentions"] == 2               # the seen one is not counted
    assert body["unread_messages"] == 2               # the one already read is not counted
    assert body["unread_direct_messages"] == 2
    assert body["total"] == 3 + 2 + 2                 # mentions are a subset of group messages, so not added again
    assert body["open_chat_reports"] == 0


def test_never_opened_class_counts_everything_in_the_window(db, world, scene, parent_client):
    """A class the parent never opened has only the 'epoch' delivery placeholder: all recent
    messages from others are unread (this is how a brand-new parent sees the group's backlog)."""
    from app.routers.class_groups import EPOCH

    rs = db.query(ClassGroupReadState).filter_by(user_id=world.parent.id).one()
    rs.last_read_at = EPOCH
    db.commit()
    body = parent_client.get("/api/notifications/summary").json()
    assert body["unread_class_group_messages"] == 5   # 2 old + 3 recent from the bursar; not own, not >90 days, not other class


def test_poll_marks_messages_delivered_and_saves_it(db, world, scene, parent_client):
    """The delivery ticks: polling is what tells the sender 'delivered'. It must still WRITE
    (and commit) when there is something new — the cheap path must not swallow real updates."""
    parent_client.get("/api/notifications/summary")
    db.expire_all()
    dms = db.query(DirectMessage).filter_by(conversation_id=scene.convo.id).all()
    assert all(m.delivered_at is not None for m in dms)
    rs = db.query(ClassGroupReadState).filter_by(user_id=world.parent.id, class_id=scene.cls.id).one()
    assert rs.last_delivered_at > _ago(minutes=2)     # was 5 hours old; newer messages existed, so it moved up to now


def test_idle_poll_writes_nothing(db, world, scene, parent_client):
    parent_client.get("/api/notifications/summary")   # delivers everything outstanding
    db.expire_all()
    before = db.query(ClassGroupReadState).filter_by(user_id=world.parent.id).one().last_delivered_at
    with _Meter() as meter:
        parent_client.get("/api/notifications/summary")
    db.expire_all()
    assert db.query(ClassGroupReadState).filter_by(user_id=world.parent.id).one().last_delivered_at == before
    assert meter.commits == 0


def test_poll_stays_within_its_round_trip_budget(scene, parent_client):
    parent_client.get("/api/notifications/summary")   # first poll may write deliveries; measure the steady state
    with _Meter() as meter:
        res = parent_client.get("/api/notifications/summary")
    assert res.status_code == 200
    # 2 tenant set_configs + class lookup + class delivery upsert + DM delivery update + ONE counts SELECT = 6.
    # It was 15. Leave a little headroom, but a number near 15 means the cost crept back.
    assert meter.round_trips <= 8, meter.statements


def test_staff_poll_is_also_cheap(db, world, scene):
    from app.core.rate_limit import limiter

    limiter.reset()
    c = TestClient(app)
    c.headers["Authorization"] = "Bearer " + create_access_token(world.bursar.id, world.school.id, "BURSAR")
    c.get("/api/notifications/summary")
    with _Meter() as meter:
        res = c.get("/api/notifications/summary")
    assert res.status_code == 200
    # Staff belong to every class group; their own messages never count, so only the parent's one is unread.
    assert res.json()["unread_class_group_messages"] == 1
    assert meter.round_trips <= 7, meter.statements

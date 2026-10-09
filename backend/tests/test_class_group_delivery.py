"""mark_class_groups_delivered() runs on every notification poll for every logged-in person, so its
"only write when something is actually new" guard has to be tied to THAT person's row.

It once wasn't: the EXISTS subquery listed class_group_read_state in its own FROM, so it scanned the
whole table instead of the row being upserted. As soon as ANYONE in the school had an undelivered
message, EVERY poll wrote — and each poll scanned the whole table (Supabase showed 150-320 ms spikes).
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.models.class_group_message import ClassGroupMessage
from app.models.class_group_read_state import ClassGroupReadState
from app.models.enums import UserRole
from app.models.school import User
from app.models.student import SchoolClass
from app.routers.class_groups import mark_class_groups_delivered
from tests.conftest import needs_db

pytestmark = needs_db

NOW = datetime.now(timezone.utc)


def _ago(**kw):
    return NOW - timedelta(**kw)


@pytest.fixture()
def scene(db, world):
    quiet, busy = SchoolClass(school_id=world.school.id, name="Grade 3"), SchoolClass(school_id=world.school.id, name="Grade 5")
    db.add_all([quiet, busy])
    other = User(school_id=world.school.id, email="other@test.example", password_hash="x", role=UserRole.PARENT, full_name="Other")
    db.add(other)
    db.flush()
    # `quiet`: last message 3h ago.  `busy`: a message 1h ago.
    db.add(ClassGroupMessage(school_id=world.school.id, class_id=quiet.id, sender_user_id=world.bursar.id, body="old", created_at=_ago(hours=3)))
    db.add(ClassGroupMessage(school_id=world.school.id, class_id=busy.id, sender_user_id=world.bursar.id, body="new", created_at=_ago(hours=1)))
    # Our parent is fully caught up on `quiet` (delivered 1h ago, after its last message).
    db.add(ClassGroupReadState(user_id=world.parent.id, class_id=quiet.id, last_read_at=_ago(hours=1), last_delivered_at=_ago(hours=1)))
    # Somebody ELSE has an undelivered message in `busy` — the thing that used to make every poll write.
    db.add(ClassGroupReadState(user_id=other.id, class_id=busy.id, last_read_at=_ago(hours=5), last_delivered_at=_ago(hours=5)))
    db.commit()
    return SimpleNamespace(quiet=quiet, busy=busy, other=other, me=SimpleNamespace(user_id=world.parent.id))


def _delivered_at(db, user_id, class_id):
    db.expire_all()
    row = db.query(ClassGroupReadState).filter_by(user_id=user_id, class_id=class_id).one_or_none()
    return row.last_delivered_at if row else None


def test_poll_writes_nothing_when_my_class_has_nothing_new_even_if_someone_elses_does(db, world, scene):
    before = _delivered_at(db, world.parent.id, scene.quiet.id)
    mark_class_groups_delivered(db, scene.me, world.school.id, class_ids={scene.quiet.id})
    assert _delivered_at(db, world.parent.id, scene.quiet.id) == before


def test_poll_records_delivery_when_my_class_has_a_newer_message(db, world, scene):
    db.add(ClassGroupReadState(user_id=world.parent.id, class_id=scene.busy.id, last_read_at=_ago(hours=5), last_delivered_at=_ago(hours=5)))
    db.commit()
    before = _delivered_at(db, world.parent.id, scene.busy.id)
    mark_class_groups_delivered(db, scene.me, world.school.id, class_ids={scene.busy.id})
    assert _delivered_at(db, world.parent.id, scene.busy.id) > before


def test_first_poll_creates_the_row(db, world, scene):
    assert _delivered_at(db, world.parent.id, scene.busy.id) is None
    mark_class_groups_delivered(db, scene.me, world.school.id, class_ids={scene.busy.id})
    assert _delivered_at(db, world.parent.id, scene.busy.id) is not None

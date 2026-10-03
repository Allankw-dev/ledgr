from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.models.refresh_token import RefreshToken
from app.services import refresh_token_service as rts
from tests.conftest import needs_db

pytestmark = needs_db


def _row(db, raw):
    return db.execute(select(RefreshToken).where(RefreshToken.token_hash == rts._hash(raw))).scalar_one()


def test_raw_token_is_never_stored(db, world):
    raw = rts.issue_refresh_token(db, world.parent)
    assert raw not in {r.token_hash for r in db.execute(select(RefreshToken)).scalars()}
    assert _row(db, raw).token_hash == rts._hash(raw)


def test_rotation_returns_user_and_new_token_same_family(db, world):
    raw = rts.issue_refresh_token(db, world.parent)
    user, new_raw = rts.rotate_refresh_token(db, raw)
    assert user.id == world.parent.id and new_raw != raw
    assert _row(db, raw).family_id == _row(db, new_raw).family_id


def test_unknown_token_rejected(db, world):
    assert rts.rotate_refresh_token(db, "definitely-not-a-token") is None


def test_reuse_after_grace_window_revokes_whole_family(db, world):
    raw = rts.issue_refresh_token(db, world.parent)
    _, newer = rts.rotate_refresh_token(db, raw)
    db.execute(update(RefreshToken).where(RefreshToken.token_hash == rts._hash(raw))
               .values(rotated_at=datetime.now(timezone.utc) - timedelta(minutes=5)))
    db.commit()
    assert rts.rotate_refresh_token(db, raw) is None  # replayed old token = theft signal
    assert rts.rotate_refresh_token(db, newer) is None  # the legitimate holder is signed out too


def test_reuse_inside_grace_window_is_allowed_for_two_tabs(db, world):
    raw = rts.issue_refresh_token(db, world.parent)
    first = rts.rotate_refresh_token(db, raw)
    second = rts.rotate_refresh_token(db, raw)  # second tab, same instant
    assert first is not None and second is not None and first[1] != second[1]


def test_password_reset_invalidates_existing_refresh_tokens(db, world):
    raw = rts.issue_refresh_token(db, world.parent)
    world.parent.token_version = 1  # what a password reset / email change does
    db.commit()
    assert rts.rotate_refresh_token(db, raw) is None


def test_deactivated_user_cannot_refresh(db, world):
    raw = rts.issue_refresh_token(db, world.parent)
    world.parent.is_active = False
    db.commit()
    assert rts.rotate_refresh_token(db, raw) is None


def test_idle_expiry_and_absolute_expiry(db, world):
    raw = rts.issue_refresh_token(db, world.parent)
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.execute(update(RefreshToken).values(expires_at=past))
    db.commit()
    assert rts.rotate_refresh_token(db, raw) is None

    raw2 = rts.issue_refresh_token(db, world.parent)
    db.execute(update(RefreshToken).where(RefreshToken.token_hash == rts._hash(raw2)).values(absolute_expires_at=past))
    db.commit()
    assert rts.rotate_refresh_token(db, raw2) is None


def test_rotation_never_outlives_the_absolute_cap(db, world):
    raw = rts.issue_refresh_token(db, world.parent)
    cap = _row(db, raw).absolute_expires_at
    _, new_raw = rts.rotate_refresh_token(db, raw)
    assert _row(db, new_raw).expires_at <= cap
    assert _row(db, new_raw).absolute_expires_at == cap


def test_logout_revokes_only_that_devices_family(db, world):
    phone = rts.issue_refresh_token(db, world.parent)
    laptop = rts.issue_refresh_token(db, world.parent)
    rts.revoke_token_family(db, phone)
    assert rts.rotate_refresh_token(db, phone) is None
    assert rts.rotate_refresh_token(db, laptop) is not None


def test_revoke_all_signs_out_every_device(db, world):
    a = rts.issue_refresh_token(db, world.parent)
    b = rts.issue_refresh_token(db, world.parent)
    rts.revoke_all_for_user(db, world.parent.id)
    db.commit()
    assert rts.rotate_refresh_token(db, a) is None and rts.rotate_refresh_token(db, b) is None

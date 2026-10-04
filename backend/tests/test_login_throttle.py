"""Per-account sign-in throttle, and what happens on a shared IP."""

import pytest
from fastapi import HTTPException

from app.core import login_throttle as lt


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    lt._local.clear()
    monkeypatch.setattr(lt, "_redis_client", lambda: None)
    yield
    lt._local.clear()


def _fail(ident, n):
    for _ in range(n):
        lt.record_failure(ident)


def test_locks_after_the_limit_and_not_before():
    _fail("a@x.com", lt.MAX_FAILURES - 1)
    assert not lt.is_locked("a@x.com")
    lt.record_failure("a@x.com")
    assert lt.is_locked("a@x.com")


def test_is_per_account_not_global():
    _fail("victim@x.com", lt.MAX_FAILURES)
    assert lt.is_locked("victim@x.com") and not lt.is_locked("someone-else@x.com")


def test_same_account_however_it_is_typed():
    _fail("Parent@X.com ", lt.MAX_FAILURES)
    assert lt.is_locked("parent@x.com")
    _fail("0712 345 678", lt.MAX_FAILURES)
    assert lt.is_locked("+254712345678") and lt.is_locked("254-712-345-678")


def test_a_correct_login_resets_the_count():
    _fail("a@x.com", lt.MAX_FAILURES - 1)
    lt.clear("a@x.com")
    _fail("a@x.com", lt.MAX_FAILURES - 1)
    assert not lt.is_locked("a@x.com")


def test_lock_expires_after_the_window(monkeypatch):
    _fail("a@x.com", lt.MAX_FAILURES)
    now = lt.time.monotonic()
    monkeypatch.setattr(lt.time, "monotonic", lambda: now + lt.WINDOW_SECONDS + 1)
    assert not lt.is_locked("a@x.com")
    lt.record_failure("a@x.com")  # a fresh window starts at 1, not at the old total
    assert not lt.is_locked("a@x.com")


def test_raw_identifier_is_never_stored():
    _fail("secret.person@school.com", 1)
    assert all("secret" not in k and "school" not in k for k in lt._local)


def test_made_up_identifiers_cannot_grow_memory_without_bound(monkeypatch):
    monkeypatch.setattr(lt.time, "monotonic", lambda: 1000.0)
    for i in range(50_001):
        lt._local[f"k{i}"] = (1, 0.0)  # all long expired
    lt.record_failure("new@x.com")
    assert len(lt._local) < 100


class FakeRedis:
    """Just the four calls the throttle makes."""
    def __init__(self): self.d, self.ttl = {}, {}
    def get(self, k): return self.d.get(k)
    def incr(self, k): self.d[k] = int(self.d.get(k, 0)) + 1; return self.d[k]
    def expire(self, k, s): self.ttl[k] = s
    def delete(self, k): self.d.pop(k, None)


def test_redis_path(monkeypatch):
    r = FakeRedis()
    monkeypatch.setattr(lt, "_redis_client", lambda: r)
    _fail("a@x.com", lt.MAX_FAILURES)
    assert lt.is_locked("a@x.com")
    assert list(r.ttl.values()) == [lt.WINDOW_SECONDS]  # expiry set once, when the window opens
    lt.clear("a@x.com")
    assert not lt.is_locked("a@x.com")


def test_redis_outage_never_blocks_sign_in(monkeypatch):
    class Broken:
        def get(self, k): raise ConnectionError("down")
        def incr(self, k): raise ConnectionError("down")
        def delete(self, k): raise ConnectionError("down")
    monkeypatch.setattr(lt, "_redis_client", lambda: Broken())
    assert lt.is_locked("a@x.com") is False
    lt.record_failure("a@x.com")
    lt.clear("a@x.com")  # none of these raise

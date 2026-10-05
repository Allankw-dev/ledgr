"""Rate limits count signed-in requests per USER, not per IP (shared school wifi / carrier addresses)."""

from types import SimpleNamespace

from app.core.rate_limit import user_or_ip_key
from app.core.security import create_2fa_challenge_token, create_access_token, create_password_reset_token


def req(auth=None, ip="10.0.0.1"):
    return SimpleNamespace(headers={"authorization": auth} if auth else {}, client=SimpleNamespace(host=ip))


def bearer(token):
    return f"Bearer {token}"


def test_signed_in_requests_are_keyed_by_user_even_from_the_same_ip():
    a = user_or_ip_key(req(bearer(create_access_token("u1", "s1", "PARENT")), ip="41.80.0.9"))
    b = user_or_ip_key(req(bearer(create_access_token("u2", "s1", "PARENT")), ip="41.80.0.9"))
    assert a == "user:u1" and b == "user:u2" and a != b


def test_same_user_on_two_devices_shares_one_allowance():
    t = create_access_token("u1", "s1", "PARENT")
    assert user_or_ip_key(req(bearer(t), ip="1.1.1.1")) == user_or_ip_key(req(bearer(t), ip="2.2.2.2"))


def test_no_token_falls_back_to_ip():
    assert user_or_ip_key(req(ip="41.80.0.9")) == "41.80.0.9"


def test_forged_garbage_or_expired_tokens_fall_back_to_ip():
    assert user_or_ip_key(req(bearer("not-a-jwt"), ip="9.9.9.9")) == "9.9.9.9"
    t = create_access_token("u1", "s1", "PARENT")
    assert user_or_ip_key(req(bearer(t[:-3] + "xyz"), ip="9.9.9.9")) == "9.9.9.9"  # bad signature
    assert user_or_ip_key(req("Basic abc", ip="9.9.9.9")) == "9.9.9.9"


def test_other_token_types_are_not_treated_as_a_session():
    assert user_or_ip_key(req(bearer(create_2fa_challenge_token("u1")), ip="7.7.7.7")) == "7.7.7.7"
    assert user_or_ip_key(req(bearer(create_password_reset_token("u1", "hash-123456")), ip="7.7.7.7")) == "7.7.7.7"

"""Token and password helpers — no database needed."""

import pytest
import jwt

from app.core import security
from app.core.config import settings


def test_access_token_round_trip():
    token = security.create_access_token("u1", "s1", "BURSAR", token_version=3)
    payload = security.decode_access_token(token)
    assert payload["sub"] == "u1" and payload["school_id"] == "s1"
    assert payload["role"] == "BURSAR" and payload["tv"] == 3


def test_tampered_or_garbage_token_rejected():
    token = security.create_access_token("u1", "s1", "BURSAR")
    with pytest.raises(ValueError):
        security.decode_access_token(token[:-2] + "xx")
    with pytest.raises(ValueError):
        security.decode_access_token("not-a-jwt")


def test_token_signed_with_other_secret_rejected():
    forged = jwt.encode({"sub": "u1", "role": "SCHOOL_ADMIN"}, "some-other-secret", algorithm="HS256")
    with pytest.raises(ValueError):
        security.decode_access_token(forged)


def test_2fa_challenge_token_is_not_an_access_token():
    """Same secret, different purpose: it must be refused as an access token (it also has no role, which
    get_current_user would reject as a second layer)."""
    challenge = security.create_2fa_challenge_token("u1")
    with pytest.raises(ValueError):
        security.decode_access_token(challenge)
    assert security.decode_2fa_challenge_token(challenge) == "u1"


def test_other_single_purpose_tokens_are_not_access_tokens_either():
    from app.core.security import create_email_change_token, create_password_reset_token

    for token in (create_password_reset_token("u1", "somehash"), create_email_change_token("u1", "new@example.com", "oldhash")):
        with pytest.raises(ValueError):
            security.decode_access_token(token)


def test_a_token_without_an_expiry_is_refused():
    """A token minted with no `exp` would otherwise be valid forever."""
    forever = jwt.encode({"sub": "u1", "school_id": "s1", "role": "BURSAR"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(ValueError):
        security.decode_access_token(forever)


def test_a_forged_unsigned_token_is_refused():
    import base64, json
    b64 = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    forged = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': 'u1', 'role': 'SUPER_ADMIN', 'exp': 9999999999})}."
    with pytest.raises(ValueError):
        security.decode_access_token(forged)


def test_a_token_signed_with_a_different_algorithm_is_refused():
    other = "HS512" if settings.jwt_algorithm != "HS512" else "HS384"
    token = jwt.encode({"sub": "u1", "role": "BURSAR", "exp": 9999999999}, settings.jwt_secret, algorithm=other)
    with pytest.raises(ValueError):
        security.decode_access_token(token)


def test_a_token_signed_with_the_wrong_secret_is_refused():
    token = jwt.encode({"sub": "u1", "role": "BURSAR", "exp": 9999999999}, "x" * 40, algorithm=settings.jwt_algorithm)
    with pytest.raises(ValueError):
        security.decode_access_token(token)


def test_access_token_cannot_be_used_as_2fa_challenge():
    access = security.create_access_token("u1", "s1", "BURSAR")
    with pytest.raises(ValueError):
        security.decode_2fa_challenge_token(access)


def test_password_reset_link_dies_after_password_changes():
    old_hash = security.hash_password("old-password")
    token = security.create_password_reset_token("u1", old_hash)
    assert security.decode_password_reset_token(token, old_hash) == "u1"
    new_hash = security.hash_password("new-password")
    with pytest.raises(ValueError):
        security.decode_password_reset_token(token, new_hash)


def test_reset_token_is_not_an_access_token_or_challenge():
    token = security.create_password_reset_token("u1", "hash-value-123456")
    with pytest.raises(ValueError):
        security.decode_2fa_challenge_token(token)


def test_email_change_token_round_trip_and_purpose_check():
    token = security.create_email_change_token("u1", "old@x.com", "New@X.com")
    user_id, new_email, fp = security.decode_email_change_token(token)
    assert (user_id, new_email) == ("u1", "New@X.com")
    assert fp == security._email_fingerprint("OLD@x.com ")  # case/space-insensitive
    with pytest.raises(ValueError):
        security.decode_email_change_token(security.create_2fa_challenge_token("u1"))


def test_expired_token_rejected(monkeypatch):
    monkeypatch.setattr(settings, "jwt_expires_minutes", -1)
    with pytest.raises(ValueError):
        security.decode_access_token(security.create_access_token("u1", "s1", "BURSAR"))


def test_verify_password():
    h = security.hash_password("s3cret!")
    assert security.verify_password("s3cret!", h)
    assert not security.verify_password("wrong", h)
    assert not security.verify_password("anything", "not-a-valid-hash")  # bad record means "no", never a 500

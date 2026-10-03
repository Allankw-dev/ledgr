import time

import pyotp

STEP_SECONDS = 30


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_provisioning_uri(secret: str, email: str, issuer: str = "Ledgr") -> str:
    """
    Returns an otpauth:// URI that authenticator apps (Google Authenticator,
    Authy, 1Password, etc.) can scan as a QR code. The QR image itself is
    rendered client-side from this string — the backend never generates or
    stores an image, just the URI.
    """
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def normalize_code(code: str) -> str:
    """Authenticator apps show codes as "123 456" and people paste them that way."""
    return "".join(ch for ch in (code or "") if ch.isdigit())


def verify_totp_code(secret: str, code: str) -> bool:
    # valid_window=1 tolerates the code from one 30-second step before/after
    # the current one, which absorbs normal clock drift between the user's
    # phone and the server without meaningfully weakening the check.
    code = normalize_code(code)
    if len(code) != 6:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def diagnose_failed_code(secret: str, code: str, max_steps: int = 20) -> int | None:
    """For SERVER LOGS ONLY — never return this to the client (it would tell an
    attacker that a guess was right for some other moment).

    A rejected code is usually one of two things: a typo, or a phone clock that
    is off. If the code would have been valid N steps (N x 30s) away from now,
    returns N, which says "the phone's clock is about N x 30 seconds off".
    Returns None if it matches nothing nearby (typo, or a different secret /
    a stale authenticator entry)."""
    code = normalize_code(code)
    if len(code) != 6:
        return None
    totp = pyotp.TOTP(secret)
    now = time.time()
    for step in range(-max_steps, max_steps + 1):
        if totp.at(now + step * STEP_SECONDS) == code:
            return step
    return None

import pyotp


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


def verify_totp_code(secret: str, code: str) -> bool:
    # valid_window=1 tolerates the code from one 30-second step before/after
    # the current one, which absorbs normal clock drift between the user's
    # phone and the server without meaningfully weakening the check.
    return pyotp.TOTP(secret).verify(code, valid_window=1)

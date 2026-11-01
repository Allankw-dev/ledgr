"""One definition of "an acceptable new password", used by every request that SETS one (school sign-up,
parent sign-up, password reset). Signing in only checks a password, so it is not subject to these rules:
people with an older password must still be able to log in and change it.

Rules, and why:
  * at least 8 characters.
  * at most 72 BYTES. bcrypt ignores everything after byte 72, so a longer password would be quietly cut
    off: two different long passwords with the same start would be the same password. Refusing is honest.
  * not one of the passwords every attacker tries first, and not a single repeated character.
"""

from typing import Annotated

from pydantic import AfterValidator, Field

from app.core.security import BCRYPT_MAX_BYTES

# Deliberately short: this is a tripwire for the obvious, not a dictionary. (All lower case; compared lower.)
_TOO_COMMON = frozenset(
    {
        "password", "password1", "password12", "password123", "passw0rd", "p@ssw0rd", "p@ssword",
        "12345678", "123456789", "1234567890", "123123123", "11111111", "00000000", "87654321",
        "qwertyui", "qwerty123", "qwertyuiop", "asdfghjk", "iloveyou", "letmein1", "welcome1",
        "welcome123", "admin123", "administrator", "abc12345", "abcd1234", "changeme", "ledgr123",
        "school123", "kenya123", "nairobi1", "monkey123", "football1", "baseball1", "superman1",
    }
)


def check_new_password(value: str) -> str:
    if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError(f"Password is too long. Use at most {BCRYPT_MAX_BYTES} bytes (about 70 characters).")
    if value.lower() in _TOO_COMMON or len(set(value)) == 1:
        raise ValueError("That password is too easy to guess. Choose something less common.")
    return value


NewPassword = Annotated[str, Field(min_length=8, max_length=200), AfterValidator(check_new_password)]

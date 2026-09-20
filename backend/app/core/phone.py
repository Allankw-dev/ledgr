"""Phone-number normalisation for logins and SMS.

Everything is stored in E.164 form ("+254712345678") so the same number typed
as 0712 345 678, 712345678, +254 712 345 678 or 254712345678 always matches
the same account. Defaults to Kenya (+254) for numbers with no country code.
"""

import re

DEFAULT_COUNTRY_CODE = "254"


def normalize_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = re.sub(r"[^\d+]", "", raw.strip())
    if not cleaned:
        return None

    if cleaned.startswith("+"):
        digits = cleaned[1:]
    elif cleaned.startswith("00"):
        digits = cleaned[2:]
    elif cleaned.startswith("0"):
        digits = DEFAULT_COUNTRY_CODE + cleaned[1:]
    elif cleaned.startswith(DEFAULT_COUNTRY_CODE) and len(cleaned) >= 12:
        digits = cleaned
    elif len(cleaned) in (9, 10) and cleaned[0] in "71":
        digits = DEFAULT_COUNTRY_CODE + cleaned
    else:
        digits = cleaned

    digits = re.sub(r"\D", "", digits)
    if not 9 <= len(digits) <= 15:
        return None
    return "+" + digits


def looks_like_email(value: str) -> bool:
    return "@" in value

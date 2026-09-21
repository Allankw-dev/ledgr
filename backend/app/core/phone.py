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


def phone_key(raw: str | None) -> str | None:
    """Canonical digits-only form used to MATCH phone numbers however they were
    typed or stored: "0712 345 678", "+254712345678", "254-712-345-678" and
    "712345678" all give "254712345678".

    MUST stay in lock-step with the SQL function ledgr_phone_key() (created in
    the a8f3c1d6e2b9 migration, backed by an index) — same rules, same order.
    """
    if not raw:
        return None
    d = re.sub(r"\D", "", raw)
    if not d:
        return None
    if d.startswith("00"):
        d = d[2:]
    elif d.startswith("0"):
        d = DEFAULT_COUNTRY_CODE + d[1:]
    elif d.startswith(DEFAULT_COUNTRY_CODE) and len(d) >= 12:
        pass
    elif len(d) in (9, 10) and d[0] in "71":
        d = DEFAULT_COUNTRY_CODE + d
    return d if 9 <= len(d) <= 15 else None

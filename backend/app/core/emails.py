"""One rule for email addresses: they are compared and stored in lower case.

Before this, sign-in, sign-up and Google sign-in matched `User.email == value` exactly, while guardian
invites were matched with lower(). So `Parent@x.com` and `parent@x.com` could become two accounts, and an
invite for one would not find the other. Every account lookup goes through `email_equals` now, and every
new account is stored with `normalize_email`. Existing mixed-case rows keep working because the lookup
lower-cases the column too.
"""

from sqlalchemy import func


def normalize_email(value: str) -> str:
    return value.strip().lower()


def email_equals(column, value: str):
    """SQL condition: `column` equals `value`, ignoring case and surrounding spaces."""
    return func.lower(column) == normalize_email(value)

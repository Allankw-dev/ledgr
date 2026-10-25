"""Create (or reset the password of) the platform operator login.

The platform operator is the person who sells Ledgr: a SUPER_ADMIN with no school of their own, who can see every
school's subscription and renew or suspend it. There is deliberately no way to become one through the website.

Run it once, from the backend folder, with the production DATABASE_URL in your .env (or exported):

    python scripts/create_super_admin.py you@example.com "Your Name"

It asks for the password; it is never taken from the command line or printed.
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.database import SystemSessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.models.school import User  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit('Usage: python scripts/create_super_admin.py you@example.com "Your Name"')
    email = sys.argv[1].strip().lower()
    name = sys.argv[2].strip() if len(sys.argv) > 2 else "Platform admin"

    password = getpass.getpass("Password (min 12 characters): ")
    if len(password) < 12:
        sys.exit("That password is too short. Use at least 12 characters.")
    if getpass.getpass("Repeat it: ") != password:
        sys.exit("The two passwords did not match.")

    with SystemSessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user and user.role != UserRole.SUPER_ADMIN:
            sys.exit(f"{email} already belongs to a school user ({user.role.value}). Use a different email.")
        if user:
            user.password_hash = hash_password(password)
            user.token_version = (user.token_version or 0) + 1  # signs out any old session
            user.is_active = True
            print(f"Updated the platform admin {email}.")
        else:
            db.add(User(school_id=None, email=email, password_hash=hash_password(password), role=UserRole.SUPER_ADMIN, full_name=name))
            print(f"Created the platform admin {email}.")
        db.commit()


if __name__ == "__main__":
    main()

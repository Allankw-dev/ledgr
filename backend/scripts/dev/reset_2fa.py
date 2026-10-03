"""Turn two-factor sign-in OFF for one account (locked-out recovery).

    cd backend
    python -m scripts.dev.reset_2fa someone@school.com

The person can sign in with just their password, then set 2FA up again from
the Security page. Connects to whatever DATABASE_URL is in .env.
"""

import sys

from sqlalchemy import func

from app.core.database import SystemSessionLocal
from app.models.school import User

if len(sys.argv) != 2:
    sys.exit("usage: python -m scripts.dev.reset_2fa <email>")

db = SystemSessionLocal()
users = db.query(User).filter(func.lower(User.email) == sys.argv[1].strip().lower()).all()
if len(users) != 1:
    sys.exit(f"expected exactly one account for that email, found {len(users)} — nothing changed")
user = users[0]
print(f"{user.full_name} ({user.role}) — 2FA was {'ON' if user.totp_enabled else 'already off'}")
user.totp_enabled = False
user.totp_secret = None
db.commit()
print("2FA is now OFF for this account.")

from dotenv import load_dotenv
load_dotenv()
import os
from sqlalchemy import create_engine, text

e = create_engine(os.environ["DATABASE_URL"])
c = e.connect()
print("mpesa_transactions table:", c.execute(text("SELECT to_regclass('public.mpesa_transactions')")).scalar())
print("messages table:", c.execute(text("SELECT to_regclass('public.messages')")).scalar())
print("alembic_version:", c.execute(text("SELECT * FROM alembic_version")).fetchall())

from dotenv import load_dotenv
load_dotenv()
import os
from sqlalchemy import create_engine, text

e = create_engine(os.environ["DATABASE_URL"])
with e.begin() as c:
    c.execute(text("DROP TYPE IF EXISTS paymentplanstatus"))
    print("Dropped orphaned enum type (if it existed).")

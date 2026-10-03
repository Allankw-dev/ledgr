import psycopg2
from app.core.config import settings as s

for name, url in [("owner (postgres)", s.database_url), ("app (ledgr_app)", s.app_database_url)]:
    if not url:
        print(name, "-> NOT SET")
        continue
    try:
        psycopg2.connect(url).close()
        print(name, "-> OK")
    except Exception as e:
        print(name, "-> FAIL:", str(e).splitlines()[0])

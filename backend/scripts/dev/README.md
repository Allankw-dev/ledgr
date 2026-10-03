# Dev / debugging scripts

One-off helpers, **not** part of the app. Run them from `backend/` as modules
(so `app.*` imports resolve and `.env` is found):

```bash
cd backend
python -m scripts.dev.check_db     # does the DB have the tables/migration we expect?
python -m scripts.dev.test_conn    # can the owner + ledgr_app roles connect?
python -m scripts.dev.diag         # schools / recent parents / students (PII masked)
python -m scripts.dev.diag2        # list students' admission numbers
python -m scripts.dev.diag3 <school_id> <admission_number>   # what RLS lets ledgr_app see
```

`fix_enum*.py` are historical repairs for orphaned Postgres enum types left behind
by a failed migration (`DROP TYPE IF EXISTS ...`). Only needed if you hit
"type ... already exists" while migrating.

They connect to whatever `DATABASE_URL` is in `.env` — check which database that is first.

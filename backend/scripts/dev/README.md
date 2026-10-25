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
python -m scripts.dev.check_gemini # does the Gemini key/model work end to end?
python -m scripts.dev.check_email you@example.com   # does email actually send from here?
```

(The old `fix_enum*.py` repair scripts were removed: they ran `DROP TYPE` against whatever
`DATABASE_URL` was in `.env`. If a failed migration ever leaves an orphaned enum type
("type ... already exists"), drop that one type by hand in the SQL editor instead.)

They connect to whatever `DATABASE_URL` is in `.env` — check which database that is first.

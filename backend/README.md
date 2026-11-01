# Ledgr backend (FastAPI)

The API behind Ledgr. For what the product does and the architecture decisions
(multi-tenancy + Row-Level Security, append-only payments, derived invoice
status), see the [top-level README](../README.md).

| Doc | What's in it |
|---|---|
| [SCALING.md](SCALING.md) | Running more than one instance: Redis, queue worker, load balancer, health checks |
| [BACKUPS.md](BACKUPS.md) | Database backup and restore |
| [MONITORING.md](MONITORING.md) | Sentry, uptime checks, `/health/status`, dead-job alerts |
| [scripts/dev/README.md](scripts/dev/README.md) | One-off debugging helpers |

## Stack

FastAPI + Uvicorn/Gunicorn · SQLAlchemy 2.0 · PostgreSQL (Supabase) · Alembic ·
PyJWT + passlib/bcrypt · slowapi (Redis-backed) · APScheduler · ReportLab ·
scikit-learn · Anthropic API · M-Pesa Daraja.

## Local setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # fill in DATABASE_URL and JWT_SECRET at minimum
alembic upgrade head
uvicorn app.main:app --reload --port 4000
```

API on `http://localhost:4000`, interactive docs at `/docs` (hidden anywhere that
isn't a developer machine: any `ENVIRONMENT` other than `development`, or running
on Render). Use the Supabase **Session pooler** URI (port 5432).

**On a live server set `ENVIRONMENT=production`, `APP_DATABASE_URL` (the restricted
`ledgr_app` role) and `CORS_ORIGINS` (your real site; `*` is refused).** See
`.env.example` and the [Security section](../README.md#security).

**Migrate before you deploy:** run `alembic upgrade head` against the database
before the new code goes live, since new code reads the columns new migrations add.

## AI assistants

Two assistants (parent chatbot, bursar "Ask Ledgr") answer from live fee data using tool calls. Set **one** of:

- `GEMINI_API_KEY` — free tier from <https://aistudio.google.com/apikey>. Free-tier requests may be used by Google to improve its products, so use a billing-enabled key once real families' data is involved.
- `ANTHROPIC_API_KEY` — Claude (paid).

`python -m scripts.dev.check_gemini` verifies the key and model end to end. Provider code lives in `app/services/llm.py`.

## Layout

```
app/
  core/       config, DB sessions + RLS context, JWT, deps, queue (jobs), idempotency, cache, locks,
              emails (case rules), body_limit (request size cap)
  models/     SQLAlchemy models
  routers/    HTTP endpoints, one file per resource
  schemas/    Pydantic request/response models
  services/   business logic (payments, invoices, refresh tokens, M-Pesa, AI, PDFs, subscriptions,
              text_safety for escaping typed text in PDFs / CSV / Excel...)
alembic/      migrations
scripts/      register_c2b_urls.py, backup_db.py, dev/ helpers
sql/          RLS + append-only audit log setup
tests/        pytest suite
loadtest/     locust load test (staging only)
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest                                  # pure-logic tests only; DB tests are skipped
```

The tests that matter most (payments, M-Pesa callbacks, reversals, idempotency,
refresh-token rotation, the job queue — including real concurrent-thread cases)
need a throwaway Postgres. **The suite drops and recreates tables**, so
`TEST_DATABASE_URL` must point at a database whose name contains `test`; anything
else is refused.

```bash
createdb ledgr_test
# Linux/macOS
export TEST_DATABASE_URL=postgresql://postgres:password@localhost:5432/ledgr_test
# Windows PowerShell
$env:TEST_DATABASE_URL = "postgresql://postgres:password@localhost:5432/ledgr_test"
pytest
```

Never point it at Supabase. The suite ignores `backend/.env` for its connection
settings, so a real `DATABASE_URL` there is not touched.

- `tests/test_route_security.py` pins every public route and every route open to any
  signed-in role. If you add a route and this fails, that is the point: decide on
  purpose, then add it to the list.
- The tenant-isolation tests run as the table owner (Row-Level Security off) to prove
  the app-level checks alone. The RLS layer itself isn't covered by the suite; see
  [Checking Row-Level Security by hand](../README.md#checking-row-level-security-by-hand).
- A test that calls a rate-limited route function directly needs a real request:
  use `fake_request()` from `tests/conftest.py`.
- Tests that go through phone matching call `install_phone_key_function(db)`, because
  the `ledgr_phone_key()` SQL function comes from a migration, not from the models.

## Money-path rules worth knowing before you edit payments

- Sessions use `autoflush=False`. `recalculate_invoice_status` flushes before it
  sums, but if you add another query that depends on an unflushed change, flush first.
- Lock the invoice (`lock_invoice`) **before** inserting a payment row that
  references it, or concurrent payments can deadlock.
- Invoice `amount_paid` = sum of `CONFIRMED` + `REVERSED` rows. A reversal keeps the
  original (`REVERSED`, +x) and adds a `CONFIRMED` correction (-x); they net to zero.

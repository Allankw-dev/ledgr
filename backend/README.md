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
python-jose + passlib/bcrypt · slowapi (Redis-backed) · APScheduler · ReportLab ·
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

API on `http://localhost:4000`, interactive docs at `/docs` (disabled when
`ENVIRONMENT=production`). Use the Supabase **Session pooler** URI (port 5432).

## Layout

```
app/
  core/       config, DB sessions + RLS context, JWT, deps, queue (jobs), idempotency, cache, locks
  models/     SQLAlchemy models
  routers/    HTTP endpoints, one file per resource
  schemas/    Pydantic request/response models
  services/   business logic (payments, invoices, refresh tokens, M-Pesa, AI, PDFs...)
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

## Money-path rules worth knowing before you edit payments

- Sessions use `autoflush=False`. `recalculate_invoice_status` flushes before it
  sums, but if you add another query that depends on an unflushed change, flush first.
- Lock the invoice (`lock_invoice`) **before** inserting a payment row that
  references it, or concurrent payments can deadlock.
- Invoice `amount_paid` = sum of `CONFIRMED` + `REVERSED` rows. A reversal keeps the
  original (`REVERSED`, +x) and adds a `CONFIRMED` correction (-x); they net to zero.

# Ledgr.

**School fee management for Kenyan schools.** Bursars get collections, overdue chasing and reconciliation in one place. Parents see what they owe and pay it over M-Pesa in a couple of taps.

[![backend tests](https://github.com/Allankw-dev/ledgr/actions/workflows/backend-tests.yml/badge.svg)](https://github.com/Allankw-dev/ledgr/actions/workflows/backend-tests.yml)
[![frontend checks](https://github.com/Allankw-dev/ledgr/actions/workflows/frontend-checks.yml/badge.svg)](https://github.com/Allankw-dev/ledgr/actions/workflows/frontend-checks.yml)

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-4169E1?logo=postgresql&logoColor=white)

---

## Contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [How it fits together](#how-it-fits-together)
- [Design decisions](#design-decisions)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [M-Pesa setup](#m-pesa-setup)
- [Testing and CI](#testing-and-ci)
- [Deploying and scaling](#deploying-and-scaling)
- [Security](#security)
- [More docs](#more-docs)
- [Status](#status)

---

## Features

Ledgr has four kinds of users: **school admins**, **bursars**, **teachers** and **parents**. A `SUPER_ADMIN` role exists for platform-level access.

### For schools (admin / bursar)

- **Students, classes, terms and fee structures**, with single or bulk invoice generation by class and term.
- **Payments**, recorded manually (cash, bank, cheque) or via M-Pesa: STK Push and direct paybill (C2B), auto-reconciled.
- **Reconciliation tools:** stray paybill payments that don't auto-match go to a review queue, and money that fits no invoice sits in an "unallocated" view until a bursar applies it, and an M-Pesa payment confirmed for a different amount than was asked waits in a "mismatch" list (nothing is credited until a bursar records or dismisses it).
- **Documents:** fee statements, itemized invoice PDFs and payment receipts.
- **Payment plans:** a risk-aware installment recommender that parents can request and staff can offer.
- **Automatic overdue reminders** by email and SMS, escalating at day 1, day 7 and day 14. Each tier is sent once per invoice.
- **Payment notifications:** guardians hear the moment a payment succeeds or fails, not just when they next open the app.
- **Messaging:** parent-to-school messages and bulk announcements.
- **"Ask Ledgr" assistant:** the bursar asks questions in plain language ("which Grade 4 students are overdue?"). It is read-only and answers only from live queries run that turn.
- **Analytics:** dashboard KPIs, collection charts and a forecast, default-risk scoring, and statistical payment-anomaly detection (Isolation Forest).
- **Audit log** of every meaningful action, with an append-only option enforced in the database.

### For parents

- One login for every child, with a combined family balance when there is more than one.
- Pay by M-Pesa, either a whole invoice, the whole balance across invoices, or a part-payment.
- Invoices, receipts and statements as downloadable PDFs.
- Request and track an installment plan.
- A parent assistant that explains why a balance exists (itemized), summarizes a term and can *preview* a payment plan. It only sees that parent's own linked children.
- Direct messages with the school office and with teachers.

### For teachers

- Class group chats (with photo and file attachments) and private teacher-to-parent chats, encrypted at rest.
- Block and report tools, with a reports queue for admins to review.

### Platform

- Email/password, Google Sign-In, TOTP two-factor and WebAuthn (fingerprint, Face ID, Windows Hello).
- Installable as a PWA (web manifest and service worker), with a mobile-first layout.
- Notification bell covering school messages, class chats, teacher chats and mentions.

---

## Tech stack

| Layer | What's used |
|---|---|
| **Backend** | FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, Python 3.12 |
| **Database** | PostgreSQL (Supabase), Row-Level Security |
| **Auth** | JWT (python-jose), bcrypt, rotating refresh tokens, pyotp, WebAuthn, Google ID tokens |
| **Background work** | Postgres-backed job queue (`FOR UPDATE SKIP LOCKED`), APScheduler for the daily sweep |
| **Payments** | M-Pesa Daraja API (STK Push + C2B), sandbox and production |
| **Messaging** | Email over HTTPS (Brevo or Resend) or SMTP, Africa's Talking SMS |
| **AI** | Gemini (free tier) or Claude via a shared provider layer, tool-calling only |
| **ML** | scikit-learn (Isolation Forest anomaly detection) |
| **Documents** | ReportLab (PDFs), openpyxl (exports) |
| **Scale and ops** | slowapi rate limiting, Redis (optional), Sentry (optional), Gunicorn |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS v4, React Router, Zustand, Axios, Recharts, react-hook-form + Zod |
| **Testing** | pytest (backend), Vitest + Testing Library (frontend), oxlint |

---

## How it fits together

```mermaid
flowchart LR
    subgraph Clients
      A[Admin / Bursar]
      T[Teacher]
      P[Parent]
    end

    A & T & P -->|HTTPS + JWT| API[FastAPI API]
    SAF[Safaricom Daraja] -->|STK + C2B callbacks<br/>secret token| API

    API -->|restricted role, RLS| DB[(PostgreSQL)]
    API -->|owner role: webhooks,<br/>login, worker| DB
    API --> STK[Daraja: STK Push]
    API --> LLM[Gemini / Claude]

    W[Job worker] -->|claims jobs| DB
    W --> SMS[Africa's Talking]
    W --> MAIL[Brevo / Resend / SMTP]
    CRON[Daily 08:00 EAT sweep] --> DB
```

Requests run as a restricted database role with Row-Level Security. Webhooks, pre-login endpoints and background jobs use a separate owner-role connection, because there is no user (and so no tenant) to scope to yet. Anything that needs to send an SMS or email is written as a job in the same transaction as the thing that triggered it, then delivered by a worker.

---

## Design decisions

Worth knowing before you change the code:

- **Multi-tenant by `school_id`, enforced twice.** Every query is scoped in the app (`get_school_scope` in `core/deps.py`) and independently in Postgres via RLS (`sql/enable_rls.sql`). A bug in one layer does not leak data past the other. Pre-authentication endpoints intentionally use the unrestricted owner connection.
- **Money is `Numeric(12, 2)`, never `Float`.**
- **Payments are append-only.** A correction is a linked reversal row, so the ledger stays fully auditable.
- **Invoice status is derived, not hand-set.** `recalculate_invoice_status` recomputes `PAID` / `PARTIALLY_PAID` / `OVERDUE` from confirmed payments every time money moves.
- **Payment, audit row and notification commit together.** Notifications use a transactional outbox (`core/jobs.py`), so a rolled-back payment never leaves a stray text behind, and a committed one never loses its notification.
- **M-Pesa is never trusted blindly.** A callback only resolves a `PENDING` payment that Ledgr created, and an amount mismatch leaves the payment pending and lists it for a bursar to record or dismiss. Duplicate callbacks are serialized with row locks. The pending payment row is written **before** the STK prompt is sent, so money can never arrive for a payment Ledgr has no record of.
- **Whole-balance payments are allocated at confirmation time**, oldest invoice first, against the balances as they are then, so a cash payment recorded mid-prompt can't cause an overpayment. Leftovers become unallocated rows for the bursar.
- **The ML features stay honest about data volume.** Risk scoring and anomaly detection are rules-based and statistical by design. Every scored invoice is logged (`invoice_risk_snapshots` + `invoice_outcomes`) so a trained model becomes possible once a school has enough resolved invoices.
- **Both assistants are tool-calling, not free-generation.** They answer only from data queried that turn. The bursar assistant is read-only. The parent assistant's tools are hard-scoped to that parent's approved children.

---

## Project structure

```
backend/
├── app/
│   ├── core/          # config, DB sessions + RLS context, JWT, deps, job queue, idempotency, cache, locks
│   ├── models/        # SQLAlchemy models, one file per concern
│   ├── routers/       # FastAPI routers, one per resource
│   ├── schemas/       # Pydantic request/response models
│   ├── services/      # business logic (payments, invoices, M-Pesa, AI, PDFs, ...)
│   ├── main.py        # app wiring, middleware, scheduler, health checks
│   └── worker.py      # stand-alone queue worker
├── alembic/versions/  # migrations
├── sql/               # RLS + append-only audit log setup
├── scripts/           # C2B URL registration, DB backup, dev helpers
├── tests/             # pytest suite
└── loadtest/          # Locust load test (staging only)

frontend/
└── src/
    ├── api/           # thin axios wrappers, one file per backend resource
    ├── components/    # shells, chat, notification bell, payment UI; ui/ holds the primitives
    ├── hooks/         # data-fetching hooks
    ├── pages/         # one file per route across the admin, teacher and parent portals
    ├── store/         # Zustand auth store
    ├── types/         # shared TS types mirroring backend schemas
    └── __tests__/     # Vitest tests
```

---

## Getting started

**Requirements:** Python 3.12, Node 22, and a Postgres database (a Supabase project works, use the **Session pooler** URI on port 5432).

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # set DATABASE_URL and JWT_SECRET at minimum
alembic upgrade head
uvicorn app.main:app --reload --port 4000
```

The API runs on `http://localhost:4000`, with interactive docs at `/docs` (disabled when `ENVIRONMENT=production`). On Windows you can also run `python run.py`.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env              # set VITE_API_URL if the backend isn't on localhost:4000
npm run dev
```

The app runs on `http://localhost:5173`. Register a school through the signup page to get a staff account, or create a parent account and link it to a student to see the parent portal.

### 3. Enable Row-Level Security (before any real data)

1. Open `backend/sql/enable_rls.sql` and set a real password in the `CREATE ROLE` line.
2. Run it once against your database as the table owner (Supabase SQL Editor, or `psql "$DATABASE_URL" -f sql/enable_rls.sql`).
3. Set `APP_DATABASE_URL` in `.env` to the `ledgr_app` role's connection string.

Without step 3 the app falls back to the owner connection: the policies exist but are not enforced. In production this logs a security error on every boot.

`enable_rls.sql` also makes the audit log append-only (rows can be added and read, never changed or deleted). If your database already has RLS set up from an older version, run `sql/audit_log_append_only.sql` once to add that.

### 4. Queue worker (optional)

By default each API process runs a job worker thread. To scale queue work separately:

```bash
RUN_JOB_WORKER=false            # on the API instances
python -m app.worker            # as its own process
```

---

## Configuration

`backend/.env.example` lists everything with explanations. At minimum you need `DATABASE_URL` and `JWT_SECRET`. Features whose variables are unset degrade gracefully (a clear "not configured" error) rather than crashing the app.

| Area | Variables |
|---|---|
| **Core** | `DATABASE_URL`, `APP_DATABASE_URL`, `JWT_SECRET`, `CORS_ORIGINS`, `FRONTEND_URL`, `ENVIRONMENT` |
| **M-Pesa** | `MPESA_CONSUMER_KEY`, `MPESA_CONSUMER_SECRET`, `MPESA_SHORTCODE`, `MPESA_PASSKEY`, `MPESA_CALLBACK_URL`, `MPESA_CALLBACK_SECRET`, `MPESA_C2B_VALIDATION_URL`, `MPESA_C2B_CONFIRMATION_URL`, `MPESA_ALLOWED_IPS` (optional) |
| **AI assistants** | `GEMINI_API_KEY` *or* `ANTHROPIC_API_KEY`, `AI_PROVIDER` (`auto` / `gemini` / `anthropic`) |
| **Email** | `BREVO_API_KEY` *or* `RESEND_API_KEY`, plus `EMAIL_FROM_EMAIL` / `EMAIL_FROM_NAME`, optionally `EMAIL_PROVIDER`. `SMTP_*` still works where outbound SMTP isn't blocked |
| **SMS** | `AFRICASTALKING_USERNAME` / `AFRICASTALKING_API_KEY` |
| **Sign-in** | `GOOGLE_CLIENT_ID` (also `VITE_GOOGLE_CLIENT_ID` in the frontend), `WEBAUTHN_RP_ID`, `WEBAUTHN_RP_NAME` |
| **Chat** | `MESSAGE_ENCRYPTION_KEYS`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` for attachments |
| **Scale and ops** | `REDIS_URL`, `SENTRY_DSN`, `MONITOR_TOKEN`, `SWEEP_HEARTBEAT_URL`, `RUN_SCHEDULER`, `RUN_JOB_WORKER` |

**Email on Render's free tier:** outbound SMTP ports (25/465/587) are blocked there, so `SMTP_*` times out. Use `BREVO_API_KEY` or `RESEND_API_KEY`, then run `python -m scripts.dev.check_email you@example.com` from a Render shell.

**Required when `ENVIRONMENT=production`** (the app refuses to start without them):

- `JWT_SECRET` of at least 32 characters
- `MPESA_CALLBACK_SECRET` of at least 24 characters
- `MESSAGE_ENCRYPTION_KEYS`, as `version:base64(32 random bytes)` entries. **Back these up: losing the key means losing the private messages.**

Free-tier Gemini requests may be used by Google to improve its products. Use a billing-enabled key once real families' data is involved. Run `python -m scripts.dev.check_gemini` to verify the key end to end.

---

## M-Pesa setup

1. Get Daraja credentials from the [Safaricom developer portal](https://developer.safaricom.co.ke/) and set the `MPESA_*` variables.
2. Generate a long random `MPESA_CALLBACK_SECRET`. Safaricom doesn't sign callbacks, so the URL itself is the secret. Put it on every URL you give Safaricom:
   ```
   MPESA_CALLBACK_URL=https://api.example.com/api/payments/mpesa/callback?token=SECRET
   ```
3. Register the C2B URLs once with `python -m scripts.register_c2b_urls` (also with `?token=SECRET`). Note Daraja rejects URLs containing the word "mpesa", which is why the C2B endpoints live under `/api/payments/c2b`.
4. For local testing, use a tunnel such as ngrok for the public callback, or set `MPESA_BASE_URL` to point at a local simulator.

Parents pay through STK Push. Payments made straight to the paybill auto-match on the student's admission number. Anything ambiguous lands in the bursar's reconciliation queue instead of being guessed at.

---

## Testing and CI

### Backend

```bash
cd backend
pip install -r requirements-dev.txt
pytest                         # pure-logic tests only; DB tests are skipped
```

The tests that matter most (payments, M-Pesa callbacks, reversals, idempotency, refresh-token rotation, tenant isolation, the job queue including concurrent-thread cases) need a throwaway Postgres. **The suite drops and recreates tables**, so `TEST_DATABASE_URL` must point at a database whose name contains `test`, and anything else is refused.

```bash
createdb ledgr_test
export TEST_DATABASE_URL=postgresql://postgres:password@localhost:5432/ledgr_test
# PowerShell: $env:TEST_DATABASE_URL = "postgresql://postgres:password@localhost:5432/ledgr_test"
pytest
```

Never point this at Supabase or any real database.

### Frontend

```bash
cd frontend
npm run lint        # oxlint
npm test            # vitest
npm run build       # typechecks (tsc -b) and builds
```

### CI

GitHub Actions runs both suites on every push and pull request that touches the relevant folder. The backend job runs against a real Postgres 16 service container.

### Money-path rules to know before editing payments

- Sessions use `autoflush=False`. `recalculate_invoice_status` flushes before it sums, but flush first if you add a query that depends on unflushed changes.
- Call `lock_invoice` **before** inserting a payment row that references the invoice, or concurrent payments can deadlock.
- An invoice's `amount_paid` is the sum of `CONFIRMED` and `REVERSED` rows. A reversal keeps the original (`REVERSED`, +x) and adds a `CONFIRMED` correction (-x), so they net to zero.

---

## Deploying and scaling

```bash
cd backend
gunicorn -c gunicorn_conf.py app.main:app      # Linux hosts (Render, Railway, a VPS, Docker)
```

The API is stateless, so several instances can run behind a load balancer. Set `REDIS_URL` so rate limits and cache are shared, point every instance at the same Postgres, and keep `workers x (pool + overflow)` under your pooler's connection limit. The daily overdue sweep (08:00 Africa/Nairobi) is guarded by a Postgres advisory lock, so only one instance does the work.

Health endpoints: `/health` (liveness), `/health/ready` (database reachable) and `/health/status?token=...` (queue backlog, dead jobs, scheduler state, hidden unless `MONITOR_TOKEN` is set).

See [`backend/SCALING.md`](backend/SCALING.md), [`backend/BACKUPS.md`](backend/BACKUPS.md) and [`backend/MONITORING.md`](backend/MONITORING.md) for details.

---

## Security

- Row-Level Security as a second tenant wall, plus per-request school scoping in the app.
- 15-minute access tokens, rotating single-use refresh tokens with reuse detection, and server-side revocation on deactivation or credential change.
- Per-account login lockout with a generous per-IP limit, rate limits on every auth endpoint, TOTP 2FA and WebAuthn.
- Guardian links must be approved before a parent sees any child data.
- Webhook secret token and optional IP allowlist on M-Pesa callbacks.
- Private teacher-to-parent chats encrypted at rest with a versioned key ring. Attachments are served through short-lived signed URLs.
- Security headers, API docs disabled in production, and no stack traces leaked to clients.

Found a vulnerability? Please report it privately rather than opening a public issue.

---

## More docs

| Doc | What's in it |
|---|---|
| [`backend/README.md`](backend/README.md) | Backend setup, AI provider config, test details |
| [`backend/SCALING.md`](backend/SCALING.md) | Running more than one instance |
| [`backend/BACKUPS.md`](backend/BACKUPS.md) | Database backup and restore |
| [`backend/MONITORING.md`](backend/MONITORING.md) | Sentry, uptime checks, dead-job alerts |
| [`backend/scripts/dev/README.md`](backend/scripts/dev/README.md) | One-off debugging helpers |
| [`frontend/README.md`](frontend/README.md) | Frontend notes |

---

## Status

Ledgr is built feature by feature rather than shipped as one release. If something here doesn't match what you find in the code, the code is more likely right. Treat this file as a map, not a contract.

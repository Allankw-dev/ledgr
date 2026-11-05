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
- **Payments**, recorded manually (cash, bank, cheque) or via M-Pesa: STK Push and direct paybill (C2B), auto-reconciled. A second prompt for an invoice that already has one pending is blocked.
- **Overpayments are held, not lost.** Money beyond what an invoice owes is kept as credit (shown to the bursar as unallocated and to the parent as "credit held") instead of silently overpaying the invoice.
- **Reconciliation tools:** stray paybill payments that don't auto-match go to a review queue, and money that fits no invoice sits in an "unallocated" view until a bursar applies it, and an M-Pesa payment confirmed for a different amount than was asked waits in a "mismatch" list (nothing is credited until a bursar records or dismisses it).
- **Documents:** fee statements, itemized invoice PDFs and payment receipts.
- **Payment plans:** a risk-aware installment recommender that parents can request and staff can offer.
- **Automatic overdue reminders** by email and SMS, escalating at day 1, day 7 and day 14. Each tier is sent once per invoice.
- **Fee aging report:** outstanding balances grouped as current, 1-30, 31-60, 61-90 and 90+ days overdue, filterable by group, with a CSV export of the full filtered list.
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
- **More than one school on one deployment.** The signup page creates the **first** school only. Every further school is added by the platform operator (a `SUPER_ADMIN`) from the *Schools and billing* page, and that school's admin gets an emailed link to set their own password. A parent who signs up is placed in the school that invited them (by phone or email), and Ledgr refuses to guess when it can't tell. See [More than one school](#5-more-than-one-school-optional).
- **Each school can have its own M-Pesa paybill.** Online M-Pesa is **off** for a new school until the operator sets it up, so its parents can never pay into another school's paybill. The operator enters the school's Daraja details in *Schools and billing > Payments*, tests them, registers the school's paybill addresses with Safaricom and switches it on. The details are stored encrypted. Direct paybill payments are routed by the paybill they were paid to, so two schools can both have a student `1001`. See [Giving a school its own paybill](#giving-a-school-its-own-paybill).
- **Subscriptions.** Each school has a plan, trial and paid-until dates and an optional learner limit. A school moves through `TRIAL` / `ACTIVE`, then `GRACE`, then `EXPIRED` (or `SUSPENDED` by the operator). Expired and suspended schools become **read-only for staff**; parents can always pay, and M-Pesa callbacks never go through the check. A learner limit stops staff adding students past it (the school keeps the learners it has).

---

## Tech stack

| Layer | What's used |
|---|---|
| **Backend** | FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, Python 3.12 |
| **Database** | PostgreSQL (Supabase), Row-Level Security |
| **Auth** | JWT (PyJWT), bcrypt (cost 12), rotating refresh tokens, pyotp, WebAuthn, Google ID tokens |
| **Background work** | Postgres-backed job queue (`FOR UPDATE SKIP LOCKED`), APScheduler for the daily sweep |
| **Payments** | M-Pesa Daraja API (STK Push + C2B), sandbox and production |
| **Messaging** | Email over HTTPS (Brevo or Resend) or SMTP, Africa's Talking SMS |
| **AI** | Gemini (free tier) or Claude via a shared provider layer, tool-calling only |
| **ML** | scikit-learn (Isolation Forest anomaly detection) |
| **Documents** | ReportLab (PDFs), openpyxl (exports) |
| **Scale and ops** | slowapi rate limiting, request-size limits, Redis (optional), Sentry (optional), Gunicorn |
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
- **Payment, audit row and notification commit together.** Notifications use a transactional outbox (`core/jobs.py`), so a rolled-back payment never leaves a stray text behind, and a committed one never loses its notification. Urgent ones (payment results, password resets) carry a higher job `priority`, so they are not stuck behind a school-wide broadcast.
- **M-Pesa is never trusted blindly.** A callback only resolves a `PENDING` payment that Ledgr created, and an amount mismatch leaves the payment pending and lists it for a bursar to record or dismiss. Duplicate callbacks are serialized with row locks. The pending payment row is written **before** the STK prompt is sent, so money can never arrive for a payment Ledgr has no record of.
- **Whole-balance payments are allocated at confirmation time**, oldest invoice first, against the balances as they are then, so a cash payment recorded mid-prompt can't cause an overpayment. Leftovers become unallocated rows for the bursar.
- **The ML features stay honest about data volume.** Risk scoring and anomaly detection are rules-based and statistical by design. Every scored invoice is logged (`invoice_risk_snapshots` + `invoice_outcomes`) so a trained model becomes possible once a school has enough resolved invoices.
- **An email address is one identity, whatever its capitalisation.** Emails are stored and compared in lower case (`core/emails.py`), backed by a unique index on `lower(email)`.
- **Typed text is escaped for the format it lands in** (`services/text_safety.py`): PDF markup, CSV/Excel formulas, email subjects. Use it for any new document or export.
- **Who can call what is pinned by tests.** `tests/test_route_security.py` lists every public route and every route open to any signed-in role. Adding one fails the build until someone reviews it on purpose.
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

The API runs on `http://localhost:4000`, with interactive docs at `/docs`. The docs are hidden anywhere that isn't a developer machine (any `ENVIRONMENT` other than `development`, or running on Render). On Windows you can also run `python run.py`.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env              # set VITE_API_URL if the backend isn't on localhost:4000
npm run dev
```

The app runs on `http://localhost:5173`. Register a school through the signup page to get a staff account (the first school only, see below), or create a parent account and link it to a student to see the parent portal.

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

### 5. More than one school (optional)

The public signup creates the first school and then refuses, from anyone, so a stranger can never open a school on a live system. Further schools are added by the **platform operator**, a `SUPER_ADMIN` with no school of their own. There is deliberately no way to become one through the website:

```bash
cd backend
python scripts/create_super_admin.py you@example.com "Your Name"    # asks for the password
```

Sign in with that account and turn on two-factor sign-in when the Platform page asks (the platform screens stay locked until it is on; if you lose the authenticator, `python -m scripts.dev.reset_2fa you@example.com`). Then open **Schools and billing**, and use **Add school**: give the school's name, its administrator's name and email, and optionally a trial length and learner limit. The administrator is emailed a link (valid for 30 minutes) to set their own password, and can use "Forgot password" later if it expires. Nobody, including the operator, ever sees or chooses that password.

A parent's school is decided by an invite the school created ("Add student" or "Link parent" with their phone or email). With one school on the deployment no invite is needed. With several and no invite, signup is refused rather than guessed.

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

**Set `ENVIRONMENT=production` explicitly on your live server.** It is what switches on the hard startup checks below. Anywhere that is not plainly a developer machine (any `ENVIRONMENT` other than `development`, or a process running on Render) already gets the safe defaults regardless: API docs hidden, HSTS, TLS required for the database connection, and a wildcard CORS origin refused. Running on Render without `ENVIRONMENT=production` logs an error on every boot.

**Required when `ENVIRONMENT=production`** (the app refuses to start without them):

- `JWT_SECRET` of at least 32 characters
- `MPESA_CALLBACK_SECRET` of at least 24 characters
- `MESSAGE_ENCRYPTION_KEYS`, as `version:base64(32 random bytes)` entries. **Back these up: losing the key means losing the private messages.**

**Also needed in production:**

- `APP_DATABASE_URL`, the restricted `ledgr_app` role. Without it the app connects as the table owner and Row-Level Security does not protect school data (logged as an error on every boot).
- `CORS_ORIGINS` listing your real site(s), comma-separated, such as `https://your-app.vercel.app`. A `*` stops the app from starting. Methods and headers are restricted to what the frontend sends, and credentials are off because no cookies are used.
- `JWT_ALGORITHM`, which only accepts `HS256`, `HS384` or `HS512`.
- On the frontend host (Vercel), `VITE_API_URL` at build time. If it is missing the bundle falls back to `http://localhost:4000`.

Free-tier Gemini requests may be used by Google to improve its products. Use a billing-enabled key once real families' data is involved. Run `python -m scripts.dev.check_gemini` to verify the key end to end.

---

## M-Pesa setup

1. Get Daraja credentials from the [Safaricom developer portal](https://developer.safaricom.co.ke/) and set the `MPESA_*` variables. Start in the **sandbox**.
2. **Sandbox vs real money.** Ledgr talks to Safaricom's *sandbox* unless you set `MPESA_BASE_URL=https://api.safaricom.co.ke`. Unset means sandbox: no real phone is prompted and no real money moves. Set it only once Safaricom has approved your paybill and you are using your **production** key, secret, shortcode and passkey. In production, Ledgr logs a warning at startup if a shortcode is set but `MPESA_BASE_URL` isn't the live address.
3. Generate a long random `MPESA_CALLBACK_SECRET`. Safaricom doesn't sign callbacks, so the URL itself is the secret. Put it on every URL you give Safaricom:
   ```
   MPESA_CALLBACK_URL=https://api.example.com/api/payments/mpesa/callback?token=SECRET
   ```
4. Register the C2B URLs once with `python -m scripts.register_c2b_urls` (also with `?token=SECRET`), once for the sandbox and again for production. Note Daraja rejects URLs containing the word "mpesa", which is why the C2B endpoints live under `/api/payments/c2b`.
5. For local testing, use a tunnel such as ngrok for the public callback, or set `MPESA_BASE_URL` to point at a local simulator.

**Where each school's money goes.** Every school has an M-Pesa mode, shown and changed under *Schools and billing > Payments*:

| Mode | What parents get |
| --- | --- |
| **Off** | No "Pay with M-Pesa" button, just a note to pay at the school's paybill. This is the default for every school the operator adds, so an unconfigured school can never pay into someone else's paybill. |
| **Server-wide paybill** | Pay into the one paybill set in the `MPESA_*` variables above (the original single-paybill setup). The first school on a deployment, and any school that already used it before this existed, starts here. |
| **This school's own paybill** | Pay into the school's own paybill, using the details saved in Ledgr. |

### Giving a school its own paybill

1. The school gets its own Daraja access from Safaricom for its paybill: a consumer key and secret, the paybill number and the passkey. Start with the sandbox. Paybills only: a Till (Buy Goods) is not supported.
2. Make sure the server is ready: `MPESA_CALLBACK_URL` is set (its host is used to build every school's addresses, and it must be `https://`), and `MESSAGE_ENCRYPTION_KEYS` is set and **backed up**, because the same keys protect the saved paybill details.
3. Sign in as the platform operator, open **Schools and billing**, then the school's **Payments** panel:
   1. Choose *Sandbox* or *Live*, enter the paybill number, key, secret and passkey, and **Save details**.
   2. **Test connection.** This checks the key and secret with Safaricom. It cannot check the paybill number or passkey; only a real payment does.
   3. **Register paybill addresses with Safaricom.** This gives Safaricom the school's own addresses for direct paybill payments. (STK pushes need no registration.)
   4. **Use this school's own paybill.** This is only possible after a successful test.
4. Make a small real payment (a few shillings) both ways: an STK push, and a direct paybill payment with the student's admission number as the account number. Confirm the money reached the school's account and that the invoice and the bursar both show it.

Good to know:

- The secrets can be replaced but never viewed again, not even by the operator.
- Editing a school's saved details switches it **off** until you test again, so payments are never left on details nobody has tried.
- Each school's addresses carry a token that only works for that school, so one school's address can never settle another school's payment. A live paybill can belong to only one school. Sandbox schools may share Safaricom's public test shortcode and are told apart by their address.
- A payment arriving for a paybill that no school owns is ignored, not credited to anyone.
- Every change is in the audit trail, without any secret.

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

The tenant-isolation tests deliberately run as the table **owner**, with Row-Level Security off, to prove the application-level school checks hold on their own. The database wall is not covered by the suite, so check it by hand whenever `sql/enable_rls.sql` changes (see below).

`tests/test_route_security.py` is a tripwire for accidental exposure: it pins every public route and every route open to any signed-in role, checks the sensitive routes are rate-limited, and covers CORS, request-size and configuration safeguards.

#### Checking Row-Level Security by hand

On a **scratch** database that has been through `alembic upgrade head`, run `sql/enable_rls.sql` as the owner (with a throwaway password on the `CREATE ROLE` line), put two schools with a student each in it, then connect as `ledgr_app` and confirm:

```sql
SELECT count(*) FROM students;                       -- 0: no school set, so nothing is visible
BEGIN;
SELECT set_config('app.current_school_id', 'A', true);
SELECT full_name FROM students;                      -- only school A's students
INSERT INTO students (id, school_id, admission_number, full_name, is_active)
  VALUES ('x', 'B', '9', 'Evil', true);              -- ERROR: violates row-level security policy
ROLLBACK;
```

The role should also be unable to `ALTER TABLE`, or to `DELETE` from `audit_logs`.

### Frontend

```bash
cd frontend
npm run lint        # oxlint
npm test            # vitest
npm run build       # typechecks (tsc -b) and builds
```

### Dependency audit

Run both now and then, and before a release:

```bash
cd backend && python -m pip install -U pip pip-audit && pip-audit      # audits the packages installed in your venv
cd frontend && npm audit
```

Upgrade `pip` first, as above: an old `pip` is itself flagged and would otherwise be the only thing in the report.

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

**Migrate first, then deploy.** New code reads the columns new migrations add, so a deploy that gets ahead of its migration fails with `column ... does not exist` on the first request. Run `alembic upgrade head` against production before the new code goes live. If your Render plan has a **Pre-Deploy Command**, set it to `alembic upgrade head` so it can't be forgotten.

The frontend deploys to Vercel. `frontend/vercel.json` sets the security headers and rewrites every path to the app. See [Security](#security) for the Content-Security-Policy.

Health endpoints: `/health` (liveness), `/health/ready` (database reachable, rate-limited per IP) and `/health/status?token=...` (queue backlog, dead jobs, scheduler state, hidden unless `MONITOR_TOKEN` is set).

See [`backend/SCALING.md`](backend/SCALING.md), [`backend/BACKUPS.md`](backend/BACKUPS.md) and [`backend/MONITORING.md`](backend/MONITORING.md) for details.

---

## Security

A full review of the code, configuration and dependencies is in [`SECURITY-AUDIT.md`](SECURITY-AUDIT.md), including a checklist of the settings only you can verify in your hosting dashboards.

**Tenants and access**
- Row-Level Security as a second tenant wall, plus per-request school scoping in the app.
- Every staff route requires a role. The routes open to any signed-in role scope the data inside the handler (an approved guardian link, class membership, your own records), and a test pins the exact list.
- Guardian links must be approved before a parent sees any child data. Parents cannot list or open student records.

**Sign-in and sessions**
- 15-minute access tokens, rotating single-use refresh tokens (stored only as hashes) with reuse detection, and server-side revocation on deactivation or credential change.
- Tokens are verified with one pinned algorithm and must carry an expiry. Reset, 2FA and email-change tokens can never be used as login tokens.
- Passwords: bcrypt (cost 12), 8 to 72 bytes (bcrypt ignores anything longer), common passwords refused, old hashes upgraded at next sign-in.
- Per-account login lockout with a generous per-IP limit, TOTP 2FA and WebAuthn.

**Abuse limits**
- Rate limits on every auth endpoint and on everything that costs money or sends a message: M-Pesa prompts, SMS and email reminders, 2FA and passkey changes.
- Request bodies are capped (1 MiB for JSON, the upload limit plus 1 MiB for uploads) and every free-text field has a maximum length.

**Data going out**
- Typed text is escaped before it reaches a PDF, and spreadsheet cells that would run as formulas (`= + - @`) are defused in CSV and Excel exports. Email subjects cannot carry line breaks.
- The frontend has no raw-HTML sinks, and links built from data only allow http, https and blob URLs.
- Uploads are checked by extension and by content, SVG is refused, and files are served through short-lived signed links with `nosniff` and a sandboxing policy.

**Transport and configuration**
- CORS allows only your site, only the methods and headers the app uses, and no credentials. JSON responses are `no-store`, HSTS is on outside development, and the database connection requires TLS.
- API docs are hidden outside development, stack traces never reach clients, and the app refuses to start in production with a weak or missing secret.
- `vercel.json` sets the frontend security headers. It **enforces** `frame-ancestors`, `base-uri` and `form-action`, and carries the full Content-Security-Policy as *Report-Only*. To enforce the full policy, open the live site with DevTools open, sign in (including with Google) and open an invoice PDF, look for CSP messages in the console, and if there are none rename the `Content-Security-Policy-Report-Only` header to `Content-Security-Policy`. (Chrome applies `object-src 'none'` to PDFs opened from `blob:` URLs, so check the PDFs first.)

**Payments and messages**
- Webhook secret token and optional IP allowlist on M-Pesa callbacks. A callback can only settle a payment Ledgr itself created.
- Each school's own M-Pesa key, secret and passkey are encrypted at rest (AES-256-GCM, bound to the school), write-only through the API, kept out of every log and the audit trail, and stored in a table the restricted database role cannot read at all, even for its own school. A school's webhook address carries a token that can only affect that school.
- Private teacher-to-parent chats encrypted at rest with a versioned key ring.

**Known limits.** Login tokens are kept in the browser's `localStorage`, so the main defence against token theft is keeping script injection out (see above). `SECURITY-AUDIT.md` lists the other accepted trade-offs.

Found a vulnerability? Please report it privately rather than opening a public issue.

---

## More docs

| Doc | What's in it |
|---|---|
| [`SECURITY-AUDIT.md`](SECURITY-AUDIT.md) | Security review: what was found and fixed, what was checked, and the pre-deploy checklist |
| [`backend/README.md`](backend/README.md) | Backend setup, AI provider config, test details |
| [`backend/SCALING.md`](backend/SCALING.md) | Running more than one instance |
| [`backend/BACKUPS.md`](backend/BACKUPS.md) | Database backup and restore |
| [`backend/MONITORING.md`](backend/MONITORING.md) | Sentry, uptime checks, dead-job alerts |
| [`backend/scripts/dev/README.md`](backend/scripts/dev/README.md) | One-off debugging helpers |
| [`frontend/README.md`](frontend/README.md) | Frontend notes |

---

## Status

Ledgr is built feature by feature rather than shipped as one release. If something here doesn't match what you find in the code, the code is more likely right. Treat this file as a map, not a contract.

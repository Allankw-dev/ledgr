# Ledgr

A school fee management platform for Kenyan schools — built for two audiences at once: bursars and admins who need to track collections and chase overdue fees, and parents who just want to know what they owe and pay it without a phone call.

## What it does

**For schools (admin/bursar side)**
- Students, classes, terms, and fee structures
- Invoice generation (single or bulk, by class/term)
- Payment recording — manual (cash/bank/cheque) and M-Pesa (STK Push *and* direct paybill/C2B, auto-reconciled)
- Fee statements, itemized invoice PDFs, payment receipts — all downloadable
- Payment plans — a risk-aware installment recommender parents can request and staff can offer
- Automatic overdue reminders (escalating: day 1, day 7, day 14) via email + SMS
- Payment confirmation notifications — a guardian hears the moment a payment succeeds or fails, not just when they check the app
- Parent-to-school messaging, and bulk announcements
- An AI assistant ("Ask Ledgr") that answers natural-language questions about collections, risk, and can send a reminder on request — grounded in real queries, not guesses
- Default-risk scoring, statistical payment-anomaly detection (Isolation Forest), and a collection forecast — see [Architecture](#architecture-notes) for how these stay honest about a small school's data volume
- Two-factor auth, an audit log of every meaningful action, and Row-Level Security enforced at the database layer (not just the API)

**For parents**
- One login, every child — a combined family balance if there's more than one
- Pay a fee via M-Pesa in a couple of taps
- Invoices, receipts, and statements, all downloadable as PDFs
- Request and track an installment plan on a balance
- A parent-facing AI assistant that explains *why* a balance exists (itemized), summarizes a term, and can preview a payment plan in conversation
- Message the school office directly

## Tech stack

**Backend** — FastAPI (Python), SQLAlchemy 2.0, PostgreSQL via Supabase, Alembic migrations, JWT auth (python-jose), bcrypt (passlib), slowapi rate limiting, APScheduler for the reminder sweep, ReportLab for PDFs, scikit-learn for the ML anomaly detector, Anthropic's API for both AI assistants.

**Frontend** — React 19 + TypeScript, Vite, Tailwind CSS v4 (CSS-based theming, no `tailwind.config.js`), React Router, Zustand for auth state, Axios, Recharts.

**Payments** — M-Pesa Daraja API (STK Push + C2B), sandbox and production.

## Architecture notes

A few decisions worth knowing before you touch the code:

- **Multi-tenant by `school_id`, enforced twice.** Every query is scoped at the application layer (`get_school_scope` in `core/deps.py`), *and* independently at the database layer via Postgres Row-Level Security (`sql/enable_rls.sql`) — a bug in one layer doesn't leak data past the other. Pre-authentication endpoints (login, registration, password reset, 2FA setup) intentionally use the unrestricted owner connection, since there's no tenant to scope to before someone's identity is established.
- **Money is `Numeric(12, 2)`, never `Float`.** No floating-point rounding surprises in currency math.
- **Payments are append-only.** Nothing in the `payments` table is edited or deleted — a correction is a linked reversal row, so the ledger stays fully auditable.
- **Invoice status is derived, not hand-set.** `recalculate_invoice_status` recomputes `PAID` / `PARTIALLY_PAID` / `OVERDUE` from actual confirmed payments every time money moves.
- **The ML features are honest about data volume.** Risk scoring and anomaly detection are rules-based/statistical by design, not black-box ML trained on too little data — but every scored invoice is logged (`invoice_risk_snapshots` + `invoice_outcomes`) so a real trained model becomes possible once a school has enough resolved invoices to learn from.
- **Both AI assistants are tool-calling, not free-generation.** The bursar and parent assistants can only answer from data they actually queried this turn — they can't fabricate a balance, and the one action either can take (sending a reminder / previewing — never creating — a payment plan) is narrow and logged.

## Project structure

```
backend/
├── app/
│   ├── core/          # config, db session + RLS context, JWT, deps
│   ├── models/         # SQLAlchemy models, one file per concern
│   ├── routers/         # FastAPI routers — one per resource
│   ├── schemas/        # Pydantic request/response models
│   └── services/        # business logic (kept out of routers)
├── alembic/versions/   # migrations
└── sql/enable_rls.sql  # Row-Level Security setup (run once per environment)

frontend/
└── src/
    ├── api/             # thin axios wrappers, one file per backend resource
    ├── components/
    │   ├── ui/           # Button, TextField, StatusBadge, StatCard, etc.
    │   ├── AppShell.tsx   # admin layout
    │   └── ParentShell.tsx # parent layout
    ├── hooks/           # data-fetching hooks
    ├── pages/           # one file per route (~20 pages across both portals)
    ├── store/           # Zustand auth store
    └── types/           # shared TS types, mirrors backend Pydantic schemas
```

## Getting started

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in DATABASE_URL and JWT_SECRET at minimum
alembic upgrade head
uvicorn app.main:app --reload --port 4000
```

API runs on `http://localhost:4000`; interactive docs at `/docs`.

**Enabling Row-Level Security** (recommended before going anywhere near real data): run `sql/enable_rls.sql` once against your database via the Supabase SQL Editor (or `psql`), set a real password in the `CREATE ROLE` line first, then set `APP_DATABASE_URL` in `.env` to that role's connection string. Without it, the app falls back to the owner connection and RLS policies exist but aren't enforced.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env     # set VITE_API_URL if the backend isn't on localhost:4000
npm run dev
```

Runs on `http://localhost:5173`. You'll need a school registered via the backend to log in as staff, or a parent account linked to a student to see the parent portal.

## Environment variables

See `backend/.env.example` for the full list with explanations. At minimum you need `DATABASE_URL` and `JWT_SECRET` to run anything; most features (M-Pesa, the AI assistants, email/SMS reminders, Google Sign-In) degrade gracefully or return a clear "not configured" error if their specific variables are left unset, rather than crashing the app.

## Status

Actively built feature-by-feature rather than shipped as one release — if something in this README describes a feature that doesn't quite match what you find in the code, the code is more likely to be right; this file gets updated in the same pass as the feature, but treat it as a map, not a contract.

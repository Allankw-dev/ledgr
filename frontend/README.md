# Ledgr — Frontend

React + TypeScript + Tailwind v4, wired to the FastAPI backend.

**Verified working**: type-checks clean and builds successfully (tested in
this sandbox — `npm run build` produces a working production bundle).

## Design identity

The visual language is drawn from the subject itself — a financial ledger:

- **Ink navy** (`#16213D`) for structure and authority, **paper white** for
  the background — a page that reads as a real financial document, not a
  generic SaaS dashboard
- **Emerald / amber / clay** carry status meaning (paid / due / overdue)
  rather than decoration
- **Fraunces** (serif) for headings gives it the weight of a ledger book;
  **Inter** for UI text; **IBM Plex Mono** for every number, with tabular
  figures so amounts actually align in columns
- The faint ruled lines behind data tables (`.ledger-lines` in `index.css`)
  are the one signature element — restrained, and it reinforces what the
  app *is* rather than decorating it

## Stack

- Vite + React 19 + TypeScript
- Tailwind CSS v4 (CSS-based theming — see `@theme` block in `src/index.css`,
  no `tailwind.config.js` needed)
- React Router for navigation
- Zustand for auth state (persisted to localStorage — just the JWT, never
  the password)
- Axios with an interceptor that attaches the JWT to every request and
  auto-logs-out on a 401

## Setup

```bash
cd frontend
npm install
cp .env.example .env     # set VITE_API_URL if your backend isn't on localhost:4000
npm run dev
```

Runs on `http://localhost:5173`. Make sure the backend (`backend-py`) is
running on port 4000 with a school registered, since login needs a real
account to authenticate against.

## Structure

```
src/
├── api/            # one file per backend resource — thin wrappers over axios
├── components/
│   ├── ui/          # design-system primitives: Button, TextField, StatusBadge, StatCard
│   └── AppShell.tsx # sidebar layout used by every authenticated page
├── hooks/          # data-fetching hooks (useDashboardData, more to come)
├── pages/          # one file per route
├── store/          # Zustand auth store
└── types/          # shared TS types, mirrors the backend's Pydantic schemas
```

## What's built so far

- Login page
- Protected routing (redirects to `/login` if not authenticated)
- Bursar dashboard: collection KPIs, outstanding balance, overdue count,
  recent invoices table

## Next

- Registration page (new school sign-up) — API call already exists in
  `api/auth.ts`, just needs the form
- Students page (list, add, view individual student ledger)
- Invoices page (bulk-generate, filter by status)
- Payment recording form
- Parent portal view (separate, simpler layout — balance + pay button)
- PWA manifest so it's installable on a parent's phone

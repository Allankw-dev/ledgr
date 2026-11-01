# Ledgr — Frontend

React + TypeScript + Tailwind v4, wired to the FastAPI backend.

Three portals in one app: school staff (admin, bursar, teacher), parents, and the
platform operator. For what the product does and how it fits together, see the
[top-level README](../README.md).

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
- Zustand for auth state, persisted to `localStorage` (the access token, the
  refresh token and the user's profile — never the password)
- Axios with an interceptor that attaches the access token to every request,
  silently swaps it using the refresh token when it expires, and signs the user
  out if that fails
- react-hook-form + Zod for forms, Recharts for charts, Sentry (optional)
- Vitest + Testing Library for tests, oxlint for linting

## Setup

```bash
cd frontend
npm install
cp .env.example .env     # set VITE_API_URL if your backend isn't on localhost:4000
npm run dev
```

Runs on `http://localhost:5173`. Make sure the backend (`backend/`) is running
on port 4000, since login needs a real account to authenticate against.

| Command | What it does |
|---|---|
| `npm run dev` | dev server |
| `npm run lint` | oxlint |
| `npm test` | Vitest, once |
| `npm run build` | type-checks (`tsc -b`) and builds |
| `npm audit` | known-vulnerability check on the dependencies |

## Structure

```
src/
├── api/            # one file per backend resource — thin wrappers over axios
├── components/     # shells (staff, parent), chat, notification bell, payment UI
│   └── ui/         # design-system primitives: Button, TextField, StatusBadge, StatCard
├── hooks/          # data-fetching hooks
├── lib/            # small pure helpers (names, receipt grouping, safeUrl, WebAuthn)
├── pages/          # one file per route
├── store/          # Zustand auth store
├── types/          # shared TS types, mirrors the backend's Pydantic schemas
└── __tests__/      # Vitest tests
public/             # PWA manifest, icons, service worker (sw.js)
vercel.json         # security headers + SPA rewrite for Vercel
```

## What's in the app

- **Staff** (admin, bursar, teacher): dashboard, students, classes, invoices,
  fee aging report, announcements and messages, guardian link requests, audit log,
  "Ask Ledgr" assistant, teachers, class group chats and chat reports, security
  settings (2FA, passkeys).
- **Parents**: dashboard with a balance per child, invoices and receipts,
  M-Pesa payment, assistant, direct chats and the class group, profile.
- **Platform operator** (`/platform`): every school's subscription, renew, suspend
  and **Add school**.
- **Everyone**: email/password and Google sign-in, forgot/reset password, email
  change confirmation, installable as a PWA with a mobile-first layout.

## Deploying (Vercel)

- **`VITE_API_URL`** (and `VITE_GOOGLE_CLIENT_ID` if you use Google sign-in) must
  be set in the Vercel project settings. Vite bakes them in at build time, and a
  missing `VITE_API_URL` makes the bundle fall back to `http://localhost:4000`.
  Everything in a `VITE_*` variable is public, so never put a secret there.
- **`vercel.json`** sets the security headers and rewrites every path to
  `index.html`. It enforces `frame-ancestors`, `base-uri` and `form-action` and
  ships the full Content-Security-Policy as *Report-Only*; the steps for
  enforcing it are in the [Security section](../README.md#security) of the main README.
- The service worker never caches `/api/` responses, so no financial data is
  left on a shared device.
- The production build publishes no source maps.

## Frontend security rules

- Don't use `dangerouslySetInnerHTML`, `innerHTML` or `eval`. There are none today.
- A URL that comes from data goes through `safeUrl()` (`src/lib/safeUrl.ts`) before it
  becomes an `href` or `src`. It only allows http, https and blob.
- Keep secrets out of the frontend. `VITE_*` values are public.
- Don't give a component a prop called `children` for something that isn't its JSX
  children (the linter flags it, and it hides real children).

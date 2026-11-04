# Ledgr security audit

Scope: the whole repository (FastAPI backend, React frontend, Vercel/Render configuration, dependencies,
git history). Method: static scanners (bandit, detect-secrets, pip-audit, npm audit), a walk of every route's
authentication / role / rate limit, manual review of the money, auth, file and export paths, and tests that
fail before each fix and pass after. Everything below was verified from a fresh clone and a virtualenv built
only from `requirements.txt` (394 backend tests, 85 frontend tests, lint, type-check and production build).

## Before you deploy: your checklist

These cannot be checked from the code; they live in your hosting dashboards.

**Run the migrations first, then deploy the code** (`alembic upgrade head` against production). The new code
reads columns the migrations add.

**Render (backend)**

| Variable | Must be |
| --- | --- |
| `ENVIRONMENT` | `production` (exactly). It enables the startup checks for secrets, M-Pesa and message encryption. |
| `APP_DATABASE_URL` | the restricted `ledgr_app` role. Without it the app connects as the table owner and Row-Level Security does not protect school data (logged as an ERROR on every boot). |
| `CORS_ORIGINS` | your real site, e.g. `https://ledgr-azure.vercel.app`. A `*` now stops the app from booting. |
| `JWT_SECRET` | 32+ random characters. |
| `MESSAGE_ENCRYPTION_KEYS`, `MPESA_CALLBACK_SECRET` | set (production refuses to start without them). |

**Vercel (frontend):** `VITE_API_URL` must be set, otherwise the bundle falls back to `http://localhost:4000`.

**Content-Security-Policy:** `vercel.json` enforces `frame-ancestors`, `base-uri` and `form-action` and
carries the full policy as *Report-Only*. To enforce the full policy: open the live site with DevTools open,
sign in (including with Google), open an invoice and a receipt PDF, and look for CSP messages in the console.
If there are none, rename the `Content-Security-Policy-Report-Only` header to `Content-Security-Policy`.
It was not switched on blindly because Chrome applies `object-src 'none'` to PDFs opened from `blob:` URLs.

## Fixed

| Area | Finding | Fix |
| --- | --- | --- |
| Access control (high) | `GET /api/students` and `/api/students/{id}` had no role check: any parent could list every child's name and admission number in the school. | Staff only. Tests: `test_access_control.py`. |
| Access control (high) | `POST /api/payments/mpesa/stk-push` checked the guardian link only `if role == PARENT`; a teacher skipped authorization and could send M-Pesa prompts for any student. | Only a linked parent, bursar or admin. |
| Injection (high) | Typed text went unescaped into ReportLab `Paragraph`. An `<img src="https://…">` in a name made the server fetch that URL while rendering invoices, receipts and statements. | `pdf_markup()` on every typed value. |
| Injection (medium) | CSV and Excel exports wrote names starting with `= + - @` as live formulas. | `csv_safe()` / `xlsx_text()`; the intentional balance and total formulas still work. |
| Injection (low) | SMTP email subjects built from typed text could carry line breaks (hidden `Bcc:`). | Flattened to one line in `send_email`. |
| Authentication (medium) | `python-jose` has an open advisory with no fixed release and no maintenance. (Not exploitable here because HS256 is pinned, but nothing can fix it.) | Replaced by PyJWT. Expiry now required on every token, tokens with a `purpose` refused as access tokens, config only accepts HS256/384/512. |
| Passwords (medium) | No upper bound: bcrypt silently ignores bytes past 72. No common-password check. Deactivated accounts skipped the hash, so they answered faster than live ones. Hash cost relied on a library default. | 8 to 72 bytes, common-password list, cost 12 set explicitly, old hashes upgraded at next login, every candidate is hashed. |
| Abuse (medium) | 39 write routes had no rate limit, including STK push, SMS/email reminders, 2FA and passkey changes. No request-size limit; 70 of 94 text fields had no maximum length. | Limits on 33 routes plus 3 public GETs. Body cap 1 MiB (uploads: limit + 1 MiB). 52 fields bounded, lists bounded, with a test that stops new unbounded fields. |
| Configuration (medium) | Docs-off, HSTS and the safe defaults depended on `ENVIRONMENT` being set exactly. CORS allowed all methods and headers with credentials. | Render counts as production for the safe defaults, wildcard CORS refused, methods and headers restricted to what the app sends, credentials off (no cookies are used), JSON responses `no-store`. |
| Database (low) | Connection fell back to unencrypted if TLS could not be negotiated. | `sslmode=require` for any non-local database unless the URL says otherwise. |
| Dependencies | pillow 12.1.1 (dozens of advisories), urllib3 2.6.3, vite, zod, undici, follow-redirects, source-map-js. `numpy`/`scikit-learn` unpinned; `cryptography` imported but not declared. | Patched or pinned. `pip-audit`: 0 vulnerabilities across 76 packages. `npm audit`: 0. Removed the unused `date-fns`. |
| Frontend | Links built from data accepted any URL scheme. `sw.js` unused parameter. | `safeUrl()` allows only http(s)/blob. Lint is at 0 warnings. |

## Checked and found sound

- **Secrets:** no real secret in the working tree or in any commit; no `.env` ever committed. All 18 scanner
  hits are placeholders or test values. Frontend `VITE_*` values are public by design (API URL, Google client ID, Sentry DSN).
- **Tenant isolation, two layers.** (1) Every school-scoped query filters by school; the automated tests run with Row-Level Security *off* specifically to prove this layer holds on its own. (2) The database wall was verified separately by applying `sql/enable_rls.sql` to a database built from the migrations and connecting as `ledgr_app`: a session that never sets a school sees nothing; school A cannot read, insert into or update school B's rows; the role cannot alter tables or delete audit-log rows. The automated suite does **not** cover layer 2, which is why the `APP_DATABASE_URL` item in the checklist matters.
- **Money path:** the pending payment is written before the STK prompt; callbacks are serialized with row locks;
  amount mismatches are parked for a person; the ledger is append-only.
- **Webhooks:** constant-time token comparison, optional IP allow-list, refuses to boot unsafe in production.
- **Sessions:** 15-minute access tokens, rotating 48-byte refresh tokens stored only as SHA-256 hashes, revocation on password change.
- **Files:** extension allow-list, magic-byte check, no SVG, size cap, path-traversal guard, signed expiring links, `nosniff` and a sandbox CSP on downloads.
- **Admin routes:** only 3 routes are `SUPER_ADMIN` (the platform ones); every staff route uses `require_roles`.
- **Build output:** no source maps, no secret-shaped strings, only public assets.

`tests/test_route_security.py` pins the exact list of the 21 public routes and the 48 routes open to any
signed-in role. Adding a new route of either kind fails the test until someone reviews it on purpose.

## Per-school M-Pesa credentials (added later)

- **Storage:** each school's consumer key, secret and passkey are encrypted with AES-256-GCM under the same key ring as
  private messages (`MESSAGE_ENCRYPTION_KEYS`), with a separate derivation per field and school. A row copied to another
  school fails to decrypt. They are write-only: no endpoint returns them, and tests search every response, log line and
  audit entry for them.
- **Access:** `school_mpesa_accounts` is owner-only. Row-Level Security is on with no policy and every privilege is
  revoked from `ledgr_app`, `anon` and `authenticated`. Verified by hand against a database built from the migrations,
  after `sql/enable_rls.sql` ran: the restricted role gets "permission denied" for select, insert, update and delete, even
  for its own school's row. Only the platform operator (`SUPER_ADMIN`) can enter or change them.
- **Isolation:** each school's webhook address carries an HMAC token for that school; a school's token cannot confirm
  another school's payment, and a paybill payment is matched only against the schools that own the paybill.
- **Safe default:** a new school's M-Pesa mode is OFF. The migration sets only the oldest existing school to the
  server-wide paybill.
- **Limits:** "Test connection" proves the key and secret, not the paybill number or passkey (only a real payment does).
  Losing `MESSAGE_ENCRYPTION_KEYS` means the saved paybill details must be entered again, so back them up. Only paybills
  are supported, not Tills.

## Accepted or open

- **Tokens live in `localStorage`.** A script-injection bug would expose them. Mitigations: no HTML sinks anywhere
  in the frontend, short access tokens, server-side refresh revocation. Enforcing the full CSP (above) is the main remaining defence.
- **No `statement_timeout`.** It cannot be set on a pooled Supabase connection through startup options without breaking connections.
- **HS256 with one shared secret.** Fine for one service; rotate `JWT_SECRET` if it is ever exposed (everyone is signed out).
- **The M-Pesa webhooks have no rate limit** on purpose: Safaricom may burst, and they are already secret-protected.
- **`GET /health/status?token=…`** puts the monitor token in a URL (it can appear in access logs). Rotate `MONITOR_TOKEN` if logs are shared.

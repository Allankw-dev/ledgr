# Ledgr monitoring setup (all free tiers)

What's built in: request logging with request IDs (`X-Request-ID`), slow/5xx warnings, Sentry error
reporting (backend + frontend), `/health` (liveness), `/health/ready` (DB), `/health/status`
(queue, dead jobs, scheduler), and a heartbeat ping after the daily reminder sweep.

## 1. Sentry (errors) — sentry.io
1. Create two projects: **ledgr-backend** (Python/FastAPI) and **ledgr-frontend** (React).
2. Render env: `SENTRY_DSN=<backend dsn>`. Vercel env: `VITE_SENTRY_DSN=<frontend dsn>`.
3. Alerts → create rule: "A new issue is created" → email you. Add a second for "issue seen > 10 times in 1h".
4. Any `logger.error(...)` also becomes a Sentry event — that's how dead jobs and M-Pesa failures alert you.

## 2. Uptime — uptimerobot.com (or Better Stack)
Generate a token: `python -c "import secrets; print(secrets.token_hex(24))"` and set Render env `MONITOR_TOKEN=<it>`.

| Monitor | URL | Interval | Alert when |
|---|---|---|---|
| API alive | `https://<render-url>/health/ready` | 5 min | not 200 |
| API deep check | `https://<render-url>/health/status?token=<MONITOR_TOKEN>` | 5 min | not 200 (503 = something needs attention; the body says what) |
| Frontend | `https://<vercel-url>` | 5 min | not 200 |

Bonus: the 5-minute ping keeps Render's free instance awake (no 30–60s cold start).

## 3. Reminder sweep heartbeat — healthchecks.io
1. New check: schedule `0 8 * * *`, timezone Africa/Nairobi, grace time 1 hour.
2. Render env: `SWEEP_HEARTBEAT_URL=<the ping URL>`. If the 08:00 sweep ever doesn't run, you get an email.

## 4. Platform dashboards worth a glance
- **Render**: Settings → Notifications → turn on "deploy failed" and "service unhealthy".
- **Supabase**: free projects pause after ~7 days of no activity — the uptime pings above prevent that. Check Database → Usage now and then (500 MB free).

## Tracing one bad request
User reports an error → get the `X-Request-ID` from the browser Network tab (or Sentry tag `request_id`) → search Render logs for it.

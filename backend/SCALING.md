# Scaling Ledgr

Short version: the API is **stateless** (every worker/instance is
interchangeable), and everything that used to live in one process's memory —
rate-limit counters, notification delivery, cache, "did we already do this"
checks, sign-in sessions — now lives in Postgres or Redis. That's what makes
it safe to run more than one instance behind a load balancer.

## What state used to be a problem, and where it lives now

| State | Old failure mode with >1 instance | Now |
|---|---|---|
| Rate limit counters | Each instance had its own counter — real limit was N× higher | Redis (`REDIS_URL`), shared across every instance |
| "Send this SMS/email" | In-memory thread pool — a crash or restart silently dropped queued work | `jobs` table (`core/jobs.py`), survives restarts, any instance can pick it up |
| Sign-in sessions | N/A — was already just a JWT | Access token (15 min) + rotating refresh token, DB-backed, works identically wherever the request lands |
| Duplicate request protection | N/A — didn't exist | `idempotency_keys` table (`core/idempotency.py`), shared |
| Dashboard cache | N/A — every request re-queried | Redis when set, else per-process with a short TTL (`core/cache.py`) — correct either way, just less effective without Redis |
| Daily overdue sweep | Would have run once per instance, sending duplicate reminders | Postgres advisory lock (`core/locks.py`) — only one instance's cron fires it |

Nothing here requires sticky sessions. Any request can land on any instance.

## Running more than one instance

1. **Set `REDIS_URL`.** Without it the app still works (rate limits and cache
   just fall back to per-process), but with more than one instance you want
   the shared behavior.
2. **Point every instance at the same Postgres.** Check your pooler's
   connection limit against `(workers per instance) × (instances) ×
   (db_pool_size + db_max_overflow)` — see the comment in `gunicorn_conf.py`.
3. **Put a load balancer in front.** Health checks:
   - `GET /health` — liveness, never touches the DB. Fast fail if the process is wedged.
   - `GET /health/ready` — readiness, checks the DB connection. Point the LB
     here so an instance that's lost its database gets taken out of rotation
     instead of serving 500s.
4. **Set `FORWARDED_ALLOW_IPS`** to your load balancer's address (or `*` if
   the LB is the only thing that can reach the app port) — otherwise every
   user appears to come from the LB's IP and shares one rate-limit bucket.
5. **Decide where the queue worker runs.** By default every instance also
   runs an in-process worker thread (`RUN_JOB_WORKER=true`). That's fine at
   small scale. Once notification volume grows enough that you want to scale
   API capacity and queue throughput independently, set
   `RUN_JOB_WORKER=false` on the API instances and run
   `python -m app.worker` as its own deployment (scale that up or down on
   its own). Either way, jobs are claimed with `FOR UPDATE SKIP LOCKED`, so
   any number of workers can run at once without double-sending anything.
6. **Only one instance's scheduler should fire the daily sweep — that's
   already handled** (see the advisory-lock row above), so you don't need to
   pick a "primary" instance by hand.

## Example: two API instances + nginx locally

```
docker compose up -d postgres redis
REDIS_URL=redis://localhost:6379 PORT=4001 gunicorn -c gunicorn_conf.py app.main:app &
REDIS_URL=redis://localhost:6379 PORT=4002 gunicorn -c gunicorn_conf.py app.main:app &
```

```nginx
upstream ledgr_api {
    server 127.0.0.1:4001;
    server 127.0.0.1:4002;
}
server {
    listen 8080;
    location /health/ready { proxy_pass http://ledgr_api; }
    location / {
        proxy_pass http://ledgr_api;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Kill either gunicorn process mid-request and the other keeps serving —
nothing above depends on which instance a request happens to land on.

## What's still a single point of failure

Postgres itself. That's normal for an app this size — use your host's
managed Postgres with its own HA/failover rather than building that here.

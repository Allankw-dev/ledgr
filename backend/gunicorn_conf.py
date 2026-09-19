"""Production server config (Linux hosts: Render, Railway, a VPS, Docker).

    gunicorn -c gunicorn_conf.py app.main:app

Windows can't run gunicorn — use `python run.py` locally.

Total DB connections = WEB_CONCURRENCY x (DB_POOL_SIZE + DB_MAX_OVERFLOW) for
the app engine, plus the same for the small system engine. Keep that under
your Supabase pooler limit when you raise the worker count.
"""
import multiprocessing
import os

bind = f"0.0.0.0:{os.getenv('PORT', '4000')}"
worker_class = "uvicorn.workers.UvicornWorker"
workers = int(os.getenv("WEB_CONCURRENCY", min(multiprocessing.cpu_count() * 2 + 1, 4)))

# Fail slow requests instead of tying up a worker forever.
timeout = 60
graceful_timeout = 30  # time to finish in-flight requests on deploy/restart
keepalive = 5

# Recycle workers periodically to cap memory growth.
max_requests = 2000
max_requests_jitter = 200

# Real client IPs for rate limiting: trust X-Forwarded-For only from these
# addresses. Set FORWARDED_ALLOW_IPS="*" when the host's proxy is the only
# thing that can reach this port (typical on Render/Railway).
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1")

accesslog = "-"
errorlog = "-"

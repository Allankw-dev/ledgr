import logging
from contextlib import asynccontextmanager

import anyio.to_thread
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from sqlalchemy.exc import OperationalError, TimeoutError as SQLAlchemyPoolTimeout
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core import background
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.database import SystemSessionLocal, engine
from app.core.locks import try_advisory_lock
from app.core.rate_limit import limiter
from app.models.school import School
from app.routers import auth, students, invoices, invoice_documents, payments, terms, fee_structures, parent, users, mpesa, c2b, receipts, reports, assistant, announcements, automation, audit_logs, parent_assistant, messages, teachers, class_groups, notifications, webauthn_auth, notifications_general, attachments, direct_messages
from app.routers.students import guardian_requests_router
from app.services.overdue_automation_service import run_overdue_reminder_sweep

logger = logging.getLogger(__name__)

# Optional error monitoring — only active when SENTRY_DSN is set.
if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.05,  # sample 5% of requests for performance traces
        send_default_pii=False,  # this is a financial app — never ship user data to third parties
    )

scheduler = BackgroundScheduler()


def run_daily_overdue_sweep() -> None:
    """Runs across every opted-in school using SystemSessionLocal — this
    fires from a background thread with no incoming request and therefore
    no JWT/tenant context for Row-Level Security to key off of, the same
    situation the M-Pesa webhook is in (see database.py's comment on
    SystemSessionLocal). Tenant isolation here comes from this function's
    own explicit school_id loop, not from RLS."""
    from sqlalchemy import select  # local import — only this scheduled job needs it

    # If several workers/instances each run the scheduler, only one of them
    # does the school loop at a time. (Each school is ALSO locked individually
    # inside run_overdue_reminder_sweep, and every reminder is recorded as
    # soon as it is sent, so a second pass finds nothing left to send.)
    with try_advisory_lock("daily-overdue-sweep") as got_lock:
        if not got_lock:
            logger.info("Daily overdue sweep already running elsewhere — skipping on this worker")
            return

        db = SystemSessionLocal()
        try:
            school_ids = db.execute(select(School.id).where(School.auto_reminders_enabled == True)).scalars().all()  # noqa: E712
            for school_id in school_ids:
                try:
                    result = run_overdue_reminder_sweep(db, school_id)
                    logger.info(
                        "Overdue reminder sweep for school %s: checked=%d sent=%d errors=%d",
                        school_id, result.invoices_checked, result.reminders_sent, len(result.errors),
                    )
                except Exception:  # noqa: BLE001 — one school's failure shouldn't stop the rest
                    logger.exception("Overdue reminder sweep failed for school %s", school_id)
                    db.rollback()  # leave the session usable for the next school
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001 — required by FastAPI's lifespan signature
    # Sync route handlers run on a shared thread pool (40 threads by default).
    # Every request waiting on the database or an SMS/email provider holds one,
    # so give it more headroom — threads are cheap, the DB pool is what limits
    # real concurrency (see db_pool_size in config.py).
    anyio.to_thread.current_default_thread_limiter().total_tokens = settings.threadpool_size

    # Runs daily at 08:00 Nairobi time. A fixed clock time (rather than "24h
    # after this process started") means restarts, deploys and recycled
    # workers can't push the sweep around or silently skip it: a run that
    # was missed by less than an hour still fires (misfire_grace_time), and
    # re-running is always safe because every reminder tier is recorded
    # per invoice the moment it's sent. A bursar can also trigger a sweep
    # immediately via POST /api/automation/run-now.
    #
    # With multiple workers/instances every one of them schedules this job,
    # but the advisory locks in run_daily_overdue_sweep / run_overdue_reminder_sweep
    # make sure only one actually does the work. Set RUN_SCHEDULER=false on an
    # instance to stop it scheduling at all.
    if settings.run_scheduler:
        scheduler.add_job(
            run_daily_overdue_sweep,
            CronTrigger(hour=8, minute=0, timezone="Africa/Nairobi"),
            id="overdue_reminder_sweep",
            coalesce=True,
            max_instances=1,
            misfire_grace_time=3600,
            replace_existing=True,
        )
        scheduler.start()
    else:
        logger.info("RUN_SCHEDULER=false — daily overdue sweep disabled on this instance")
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)
    background.shutdown()


# Interactive API docs list every endpoint and its schema — handy in dev, a
# free map of the attack surface in production.
_docs_kwargs = (
    {"docs_url": None, "redoc_url": None, "openapi_url": None} if settings.environment == "production" else {}
)
app = FastAPI(title="Ledgr API", version="0.1.0", lifespan=lifespan, **_docs_kwargs)

# Rate limiting — auth endpoints are the prime brute-force target, and are
# decorated individually in app/routers/auth.py (@limiter.limit(...)).
# This MUST be the same Limiter instance those decorators use — importing
# from app.core.rate_limit rather than constructing a second one here is
# what makes that true; two separate Limiter() instances would silently
# not rate-limit anything, since slowapi checks against app.state.limiter.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Resolve the real client IP from X-Forwarded-For (for rate limiting and audit
# logs). Done here, in the app, rather than trusting each server launcher to
# do it: under gunicorn's uvicorn worker the launcher-level setting was NOT
# taking effect and every user appeared as 127.0.0.1 — one shared bucket.
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=settings.forwarded_allow_ips)

# Compress larger JSON responses (lists, analytics) — big bandwidth savings on
# slow mobile connections. Small responses are left alone.
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(OperationalError)
@app.exception_handler(SQLAlchemyPoolTimeout)
async def database_unavailable_handler(request: Request, exc: Exception):  # noqa: ARG001
    # Database unreachable or the connection pool is saturated. A 503 with
    # Retry-After tells clients (and load balancers) this is temporary, rather
    # than a generic 500 that looks like a bug in the request.
    logger.error("Database unavailable: %s", exc.__class__.__name__)
    return JSONResponse(
        status_code=503,
        content={"error": "Service temporarily unavailable, please try again shortly"},
        headers={"Retry-After": "5"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):  # noqa: ARG001
    # Never leak stack traces or internals to the client
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


app.include_router(auth.router)
app.include_router(students.router)
app.include_router(invoices.router)
app.include_router(invoice_documents.router)
app.include_router(payments.router)
app.include_router(terms.router)
app.include_router(terms.classes_router)
app.include_router(fee_structures.router)
app.include_router(parent.router)
app.include_router(users.router)
app.include_router(mpesa.router)
app.include_router(c2b.router)
app.include_router(guardian_requests_router)
app.include_router(receipts.router)
app.include_router(reports.router)
app.include_router(assistant.router)
app.include_router(announcements.router)
app.include_router(automation.router)
app.include_router(audit_logs.router)
app.include_router(parent_assistant.router)
app.include_router(messages.router)
app.include_router(teachers.router)
app.include_router(class_groups.router)
app.include_router(notifications.router)
app.include_router(notifications_general.router)
app.include_router(attachments.router)
app.include_router(direct_messages.router)
app.include_router(webauthn_auth.router)


@app.get("/health")
def health():
    """Liveness — is the process up? Cheap, never touches the database."""
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready():
    """Readiness — can this instance actually serve requests? Point your
    load balancer / uptime monitor here so a worker that has lost its
    database is taken out of rotation instead of returning errors."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "database unavailable"})
    return {"status": "ok"}

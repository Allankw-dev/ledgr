import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.background import BackgroundScheduler
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.database import SystemSessionLocal
from app.core.rate_limit import limiter
from app.models.school import School
from app.routers import auth, students, invoices, invoice_documents, payments, terms, fee_structures, parent, users, mpesa, c2b, receipts, reports, assistant, announcements, automation, audit_logs, parent_assistant, messages, teachers, class_groups
from app.routers.students import guardian_requests_router
from app.services.overdue_automation_service import run_overdue_reminder_sweep

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def run_daily_overdue_sweep() -> None:
    """Runs across every opted-in school using SystemSessionLocal — this
    fires from a background thread with no incoming request and therefore
    no JWT/tenant context for Row-Level Security to key off of, the same
    situation the M-Pesa webhook is in (see database.py's comment on
    SystemSessionLocal). Tenant isolation here comes from this function's
    own explicit school_id loop, not from RLS."""
    from sqlalchemy import select  # local import — only this scheduled job needs it

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
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001 — required by FastAPI's lifespan signature
    # interval, not cron, so restarts don't need to reason about "did today's
    # run already happen" — it simply runs every 24h from whenever the
    # process started. A bursar can also trigger a sweep immediately via
    # POST /api/automation/run-now instead of waiting for this.
    scheduler.add_job(run_daily_overdue_sweep, "interval", hours=24, id="overdue_reminder_sweep")
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Ledgr API", version="0.1.0", lifespan=lifespan)

# Rate limiting — auth endpoints are the prime brute-force target, and are
# decorated individually in app/routers/auth.py (@limiter.limit(...)).
# This MUST be the same Limiter instance those decorators use — importing
# from app.core.rate_limit rather than constructing a second one here is
# what makes that true; two separate Limiter() instances would silently
# not rate-limit anything, since slowapi checks against app.state.limiter.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/health")
def health():
    return {"status": "ok"}

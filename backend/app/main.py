from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.rate_limit import limiter
from app.routers import auth, students, invoices, payments, terms, fee_structures, parent, users, mpesa, receipts, reports, assistant
from app.routers.students import guardian_requests_router

app = FastAPI(title="Ledgr API", version="0.1.0")

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
app.include_router(payments.router)
app.include_router(terms.router)
app.include_router(terms.classes_router)
app.include_router(fee_structures.router)
app.include_router(parent.router)
app.include_router(users.router)
app.include_router(mpesa.router)
app.include_router(guardian_requests_router)
app.include_router(receipts.router)
app.include_router(reports.router)
app.include_router(assistant.router)


@app.get("/health")
def health():
    return {"status": "ok"}

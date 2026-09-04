from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from app.core.config import settings

# Requests are served through app_database_url (the restricted ledgr_app role)
# when configured, so Row-Level Security policies actually apply. Falling
# back to database_url keeps the app working before RLS is set up, but that
# path connects as the table owner — see sql/enable_rls.sql to close this.
_runtime_url = settings.app_database_url or settings.database_url
if not settings.app_database_url:
    import warnings

    warnings.warn(
        "APP_DATABASE_URL is not set — the app is connecting with the same "
        "role that owns the tables, so Row-Level Security policies (if any) "
        "will not be enforced. Run sql/enable_rls.sql and set APP_DATABASE_URL "
        "in .env to close this gap.",
        stacklevel=1,
    )

# pool_pre_ping avoids "server closed the connection unexpectedly" errors
# after Supabase idles a connection out — the classic cause of intermittent
# 500s in apps that don't set this.
engine = create_engine(_runtime_url, pool_pre_ping=True, pool_size=10, max_overflow=20)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# A second engine, deliberately using the OWNER role (database_url, not the
# restricted app_database_url), for trusted system/webhook endpoints like
# the M-Pesa Daraja callback. Those requests are never authenticated with a
# user JWT — Safaricom calls them directly — so get_school_scope never runs
# and RLS would have no tenant context to check against, silently hiding
# the very row the callback needs to update. Their security instead comes
# from matching an unguessable CheckoutRequestID that WE generated during
# the STK push — a different, still-valid trust model, just not one RLS
# understands. Use get_system_db() ONLY for endpoints with that kind of
# alternative security guarantee, never as a shortcut to avoid tenant checks
# elsewhere.
_system_engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=10)
SystemSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_system_engine)

Base = declarative_base()


@event.listens_for(Session, "after_begin")
def _reapply_tenant_context(session, transaction, connection):
    """
    Row-Level Security relies on set_config(..., is_local=true), which is
    scoped to a single Postgres transaction. A request that commits more
    than once (e.g. db.commit() after creating a row, then db.refresh()
    reading it back) starts a NEW transaction on that second query — and
    without this listener, the tenant context from the first transaction
    would already be gone, so RLS would silently block the app from seeing
    the row it just inserted.

    Reads from session.info (a plain dict attribute on the Session object)
    rather than a ContextVar — FastAPI dispatches each sync dependency and
    the sync route handler as SEPARATE calls to run_in_threadpool, each
    getting its own independent copy of any ContextVar, so a value set in
    one (e.g. inside get_school_scope) is invisible in another (e.g. inside
    the route handler). session.info has no such problem: db is the same
    shared Session object across the whole request regardless of which
    thread touches it, so a plain attribute on it is visible everywhere.
    """
    school_id = session.info.get("school_id")
    if school_id:
        connection.execute(
            text("SELECT set_config('app.current_school_id', :school_id, true)"),
            {"school_id": school_id},
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_system_db():
    """For trusted system/webhook endpoints only — see the comment on
    SystemSessionLocal above for exactly when this is and isn't appropriate."""
    db = SystemSessionLocal()
    try:
        yield db
    finally:
        db.close()

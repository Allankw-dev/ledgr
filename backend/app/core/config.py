from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase Postgres connection string (use the Session pooler URI —
    # SQLAlchemy doesn't need the pgbouncer transaction-mode URL the way
    # Prisma does, since it manages its own connection pool)
    database_url: str

    # Runtime connection for serving requests, using the restricted ledgr_app
    # role created by sql/enable_rls.sql — this role cannot bypass Row-Level
    # Security, unlike the role above (which owns the tables and is used for
    # migrations). Falls back to database_url if not set, so the app still
    # runs before RLS is set up — but the second security wall only takes
    # effect once this is configured.
    app_database_url: str | None = None

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24 * 7  # 7 days

    cors_origins: str = "http://localhost:5173"

    # Base URL of the deployed frontend — used to build links inside emails
    # (password reset, guardian invites) that need to point back at the app
    # rather than the API. Defaults to the local Vite dev server.
    frontend_url: str = "http://localhost:5173"

    # Phase 2 — M-Pesa Daraja
    mpesa_base_url: str | None = None  # override for local testing, e.g. Pesa Playground — see mpesa_service.py
    mpesa_consumer_key: str | None = None
    mpesa_consumer_secret: str | None = None
    mpesa_shortcode: str | None = None
    mpesa_passkey: str | None = None
    mpesa_callback_url: str | None = None  # public HTTPS URL Safaricom calls back to
    # C2B — for payments made directly to the paybill, not via our STK push.
    # Registered ONCE with Safaricom via scripts/register_c2b_urls.py, not
    # called by the app itself, but read here for that script to use.
    mpesa_c2b_validation_url: str | None = None
    mpesa_c2b_confirmation_url: str | None = None

    # AI assistant — powers the parent chatbot and the bursar's "Ask Ledgr" assistant
    anthropic_api_key: str | None = None

    # "Sign in with Google" — the OAuth client ID Google issues; ID tokens are
    # verified against this as the audience. No client secret needed since
    # this flow only ever handles a frontend-obtained ID token, never a
    # server-side authorization-code exchange.
    google_client_id: str | None = None

    # Reminders — email via SMTP, SMS via Africa's Talking
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str = "Ledgr"

    africastalking_username: str | None = None
    africastalking_api_key: str | None = None
    africastalking_sandbox: bool = True

    class Config:
        env_file = ".env"


settings = Settings()  # type: ignore[call-arg]
